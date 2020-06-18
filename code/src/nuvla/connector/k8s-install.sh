#!/bin/bash
set -ex

ROLE=${1:?"Role: manager or worker"}

K8S_VER=1.18.0-00

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

sudo apt-get update
sudo sudo apt-get install -y apt-transport-https
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg \
    | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
cat <<EOF | sudo tee /etc/apt/sources.list.d/kubernetes.list
deb https://apt.kubernetes.io/ kubernetes-xenial main
EOF
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 6A030B21BA07F4FB
sudo apt-get update
sudo apt-get install -y kubelet=$K8S_VER kubeadm=$K8S_VER
if [ "$ROLE" == "manager" ]; then
    sudo apt-get install -y --allow-downgrades kubectl=$K8S_VER
    sudo kubeadm init --pod-network-cidr=10.244.0.0/16
    mkdir $HOME/.kube
    sudo cp /etc/kubernetes/admin.conf /home/ubuntu/.kube/config
    sudo chown ubuntu. .kube/config
    kubectl cluster-info
    KF=https://raw.githubusercontent.com/coreos/flannel/a70459be0084506e4ec919aa1c114638878db11b/Documentation/kube-flannel.yml
    kubectl apply -f $KF | tee pod_network_setup.txt
fi
