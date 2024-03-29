from typing import Optional
import os
import re
from subprocess import Popen, PIPE
import json

from docker.tls import TLSConfig
from .helper import which

LS_FIELDS = ["Name", "Active", "ActiveHost", "ActiveSwarm", "DriverName", "State", "URL", "Swarm", "Error",
             "DockerVersion", "ResponseTime"]


class Machine:
    def __init__(self, binary="docker-machine"):
        """
        Args:
            binary (str): path to docker-machine binary
        """
        self._path = None
        self.binary = binary

    @property
    def path(self):
        if self._path is None:
            where = which(self.binary)
            if not where:
                raise RuntimeError("Cant find docker-machine binary (%s)" % self.binary)
            self._path = where
        return self._path

    def _run(self, cmd, raise_error=True, env_extra: Optional[dict]=None, blocking: bool=False, machine_name: str=None):
        """
        Run a docker-machine command, optionally raise error if error code != 0

        Args:
            cmd (List[str]): a list of the docker-machine command with the arguments to run
            raise_error (bool): raise an exception on non 0 return code
        Returns:
            tuple: stdout, stderr, error_code
        """
        cmd = [self.path] + cmd
        if env_extra:
            p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                      env={**env_extra, **os.environ})
        else:
            p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        error_code = p.wait() if blocking else p.returncode

        if error_code:
            if "There was an error validating certificates" in stderr.decode('utf-8').strip():
                name = machine_name if machine_name else cmd[-1]
                recovery_cmd = [self.path] + ["regenerate-certs", "-f", name]
                if env_extra:
                    rp = Popen(recovery_cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                              env={**env_extra, **os.environ})
                else:
                    rp = Popen(recovery_cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
                stdout, stderr = rp.communicate()
                error_code = rp.wait() if blocking else rp.returncode

            if raise_error and error_code:
                raise RuntimeError(f"cmd returned error {error_code}: {stderr.decode('utf-8').strip()}")
        return stdout.decode('utf-8'), stderr.decode('utf-8'), error_code

    def _match(self, cmd, regexp):
        """
        Run cmd and match regular expression regexp on it, return results.

        Args:
            cmd (List[str]): docker-machine command to run
            regexp (str): regular expression to match with
        Return:
            bool or regexp match
        """
        stdout, stderr, errorcode = self._run(cmd)
        cleaned = stdout.strip()
        match = re.match(regexp, cleaned)
        if not match:
            raise RuntimeError("can't parse output (\"%s\")" % cleaned)
        return match

    def version(self):
        """
        Get the docker-machine binary version.

        Returns:
            str: the docker-machine binary version

        """
        cmd = ["version"]
        regexp = "docker-machine version (.+), build (.+)"
        match = self._match(cmd, regexp)
        return match.group(1)

    def create(self, name, driver='virtualbox', blocking=True, xarg=None, env=None):
        """
        Create a docker machine using the provided name and driver
        NOTE: This takes a loooooong time

        Args:
            name (str): the name to give to the machine (must be unique)
            driver: the driver to use to create the machine
            blocking (bool): should wait for completion before exiting

        Returns:
            int: error code from the run
        """
        if xarg is None:
            xarg = []
        cmd = ['create', '--driver', driver] + xarg + [name]

        stdout, stderr, errorcode = self._run(cmd, env_extra=env, blocking=blocking, machine_name=name)

        return errorcode

    def config(self, machine="default"):
        """
        Returns the docker configuration for the given machine.

        Args:
            machine: The machine name
        Returns:
            dict: base_url, tls
        """
        cmd = ["config", machine]
        regexp = """(--tlsverify\n)?--tlscacert="(.+)"\n--tlscert="(.+)"\n--tlskey="(.+)"\n-H=(.+)"""
        match = self._match(cmd, regexp)
        tlsverify, tlscacert, tlscert, tlskey, host = match.group(1, 2, 3, 4, 5)
        tlsverify = bool(tlsverify)

        params = {
            'base_url': host.replace('tcp://', 'https://') if tlsverify else host,
            'tls': TLSConfig(
                client_cert=(tlscert, tlskey),
                ca_cert=tlscacert,
                verify=True
            )
        }
        return params

    def ls(self):
        """
        List machines.

        Returns:
            list: of machines
        """
        seperator = "\t"
        fields = seperator.join(["{{.%s}}" % i for i in LS_FIELDS])
        cmd = ["ls", "-f", fields]
        stdout, stderr, errorcode = self._run(cmd)
        machines = []
        for line in stdout.split("\n"):
            machine = {LS_FIELDS[index]: value for index, value in enumerate(line.split(seperator))}
            machines.append(machine)
        return machines

    def exists(self, machine="default"):
        """
        Checks if machine exists.

        Args:
            machine (str): name of the machine
        Returns:
            bool
        """
        cmd = ["ls", "--filter", "NAME=" + machine, "--format", "{{.Name}}"]
        stdout, _, _ = self._run(cmd)
        for line in stdout.split('\n'):
            if line == machine:
                return True
        return False

    def status(self, machine="default", env=None):
        """
        Get the status for the machine.

        Args:
            machine (str): the name of the machine

        Returns:
            bool: status of machine

        """
        cmd = ["status", machine]
        stdout, _, _ = self._run(cmd, env_extra=env)
        return stdout.strip() == "Running"

    def stop(self, machine="default", env=None):
        """
        Stop the specified machine.

        Args:
            machine (str): the name of the machine
        """
        cmd = ["stop", machine]
        self._run(cmd, env_extra=env)
        return True

    def start(self, machine="default", env=None):
        """
        Start the specified machine.

        Args:
            machine (str): the name of the machine
        Returns:
            bool: True if successful
        """
        cmd = ["start", machine]
        self._run(cmd, env_extra=env)
        return True

    def provision(self, machine="default"):
        """
        Provision the specified machine.

        Args:
            machine (str): the name of the machine
        Returns:
            bool: True if successful
        """
        cmd = ["provision", machine]
        self._run(cmd)
        return True

    def regenerate_certs(self, machine="default"):
        """
        Regenerate certificats for the specified machine.

        Args:
            machine (str): the name of the machine
        Returns:
            bool: True if successful
        """
        cmd = ["regenerate-certs", "--force", machine]
        self._run(cmd)
        return True

    def rm(self, machine="default", force=False, env=None):
        """
        Remove the specified machine.

        Args:
            machine (str): the name of the machine
            force (bool): Remove local configuration even if machine cannot be removed
        Returns:
            bool: True if successful
        """
        f = ["-f"] if force else []
        cmd = ["rm", "-y"] + f + [machine]
        self._run(cmd, env_extra=env)
        return True

    def env(self, machine="default"):
        """
        Get the environment variables to configure docker to connect to the specified docker machine.

        Args:
            machine (str): the name of the machine
        Returns:
            str: A set of environment variables
        """
        cmd = ["env", machine]
        stdout, _, _ = self._run(cmd)
        return stdout.split('\n')

    def inspect(self, machine="default"):
        """
        Inspect information about a machine.

        Args:
            machine (str): the name of the machine
        Returns:
            dict: A nested dicht with inspect information about the machine.
        """
        cmd = ["inspect", machine]
        stdout, _, _ = self._run(cmd)
        return json.loads(stdout)

    def ip(self, machine="default", env=None):
        """
        Get the IP address of a machine.

        Args:
            machine (str): the name of the machine
        Returns:
            str: the IP address of a machine.
        """
        cmd = ["ip", machine]
        stdout, _, _ = self._run(cmd, env_extra=env)
        return stdout.strip()

    def kill(self, machine="default"):
        """
        Kill a machine

        Args:
            machine (str): the name of the machine
        Returns:
            bool: True if successful
        """
        cmd = ["kill", machine]
        self._run(cmd)
        return True

    def restart(self, machine="default"):
        """
        Restart a machine

        Args:
            machine (str): the name of the machine
        Returns:
            bool: True if successful
        """
        cmd = ["restart", machine]
        self._run(cmd)
        return True

    def upgrade(self, machine="default"):
        """
        Upgrade a machine

        Args:
            machine (str): the name of the machine
        Returns:
            bool: True if successful
        """
        cmd = ["upgrade", machine]
        self._run(cmd)
        return True

    def url(self, machine="default", env=env):
        """
        Get the URL of a machine

        Args:
            machine (str): the name of the machine
        Returns:
            str: the URL of a machine
        """
        cmd = ["url", machine]
        stdout, _, _ = self._run(cmd, env_extra=env)
        return stdout.strip()

    def active(self):
        """
        Print which machine is active

        Returns:
            List[str]: a list of machines that are active
        """
        cmd = ["active"]
        stdout, stderr, error_code = self._run(cmd, raise_error=False)
        if error_code == 1 and stderr.strip() == "No active host found":
            return None
        return stdout.strip()

    def scp(self, source, destination, recursive=False, env=None):
        """
        Copy files between machines

        Args:
            source (str): [machine:][path]
            destination (str): [machine:][path]
            recursive (bool):  Copy files recursively (required to copy directories)

        Returns:
            List[str}: output of the scp command
        """
        r = ["-r"] if recursive else []
        cmd = ["scp"] + r + [source, destination]
        stdout, stderr, exit_code = self._run(cmd, env_extra=env)
        return stdout,

    def ssh(self, machine, cmd, env=None):
        """
        Run a command on a machine through docker-machine ssh

        Args:
            machine (str): machine name
            cmd (str): command to run

        Returns:
            List[str]: output of the ssh command
        """
        ssh_cmd = ['ssh', machine, cmd]
        stdout, _, _ = self._run(ssh_cmd, env_extra=env)
        return stdout.split('\n')
