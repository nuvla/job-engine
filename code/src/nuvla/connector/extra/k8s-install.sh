#!/bin/bash
set -ex

ROLE=${1:?"Role: manager or worker"}
# Extra Subject Alternative Names for the API server.
EXTRA_SANS=${2}

K8S_VER=1.19.5-00

# "Fix" docker daemon: https://github.com/kubernetes/kubeadm/issues/1394#issuecomment-462878219
cat > /tmp/daemon.json <<EOF
{
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m"
  }
}
EOF
sudo mv /tmp/daemon.json /etc/docker/daemon.json
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo systemctl daemon-reload
sudo systemctl restart docker

sudo sh -c "echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections"
sudo apt-get update
sudo apt-get install dialog apt-utils -y -q

sudo sudo apt-get install -y apt-transport-https
sudo curl https://packages.cloud.google.com/apt/doc/apt-key.gpg --output /etc/apt/trusted.gpg.d/k8s-apt-key.gpg
sudo apt-add-repository "deb http://apt.kubernetes.io/ kubernetes-xenial main" -y
sudo apt update
sudo apt-get install -y kubelet=$K8S_VER kubeadm=$K8S_VER kubectl=$K8S_VER

if [ "$ROLE" == "manager" ]; then
    sudo apt-get install -y --allow-downgrades kubectl=$K8S_VER
    if [ ! -z "${EXTRA_SANS}" ]; then
      sudo kubeadm init --pod-network-cidr=10.244.0.0/16 --apiserver-cert-extra-sans "$EXTRA_SANS"
    else
      sudo kubeadm init --pod-network-cidr=10.244.0.0/16
    fi
    mkdir -p $HOME/.kube
    sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
    export user_name=$(id -u -n)
    sudo chown $user_name:$user_name $HOME/.kube/config
    kubectl cluster-info
    KF=https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml
    kubectl apply -f $KF 2>&1 | tee pod_network_setup.txt
fi
