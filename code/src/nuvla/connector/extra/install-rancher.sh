#!/bin/bash

set -x
set -e

export KUBECONFIG=${1:-~/.kube/config}

curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3
chmod 700 get_helm.sh
sudo ./get_helm.sh

helm repo add rancher-latest https://releases.rancher.com/server-charts/latest

kubectl create namespace cattle-system

# Install the CustomResourceDefinition resources separately
kubectl apply --validate=false -f https://github.com/jetstack/cert-manager/releases/download/v0.15.0/cert-manager.crds.yaml

# Create the namespace for cert-manager
kubectl create namespace cert-manager

# Add the Jetstack Helm repository
helm repo add jetstack https://charts.jetstack.io

# Update local Helm chart repository cache
helm repo update

# Install the cert-manager Helm chart
helm install \
      cert-manager jetstack/cert-manager \
        --namespace cert-manager \
          --version v0.15.0

helm install rancher rancher-latest/rancher \
      --namespace cattle-system \
        --set replicas=1 \
        --set hostname=example.com || true

kubectl -n cattle-system rollout status deploy/rancher

cat >service-nodeport.yaml<<EOF
---
kind: Service
apiVersion: v1
metadata:
  name: rancher-public
spec:
  type: NodePort
  selector:
    app: rancher
  ports:
  - protocol: TCP
    name: https
    port: 443
    targetPort: 443
    nodePort: 31443
EOF
kubectl -n cattle-system create -f service-nodeport.yaml
