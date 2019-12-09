#!/Users/khaledbasbous/nuvla_py3/bin/python

from nuvla.connector.kubernetes_cli_connector import KubernetesCliConnector

cert="""-----BEGIN CERTIFICATE-----
MIIDADCCAeigAwIBAgIBAjANBgkqhkiG9w0BAQsFADAVMRMwEQYDVQQDEwptaW5p
a3ViZUNBMB4XDTE5MTEyNjE1MTY0MloXDTIwMTEyNjE1MTY0MlowMTEXMBUGA1UE
ChMOc3lzdGVtOm1hc3RlcnMxFjAUBgNVBAMTDW1pbmlrdWJlLXVzZXIwggEiMA0G
CSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCyFlv89Vef50geug1Zwkhs+ZCY2PiQ
CUxV92KUzJ48xjAAC/1p65adVhUu69BFpd6xbjVaKXHKR25JETkvsWnv76lDdcdk
uBb/YzoJ6Fj34G6xN9HPgn+yjoJFdHswNwEGW/Mf4ncH4C23UewHp94VwdQLaalt
+OI2l+1dxLiH7Tjoej9JKpdKBWGaF4EprWXnDWo1KhNA+j2nK5Mjn4mLYii0V1oc
QZ/QuCfeY/tRBeLO4LsbFGNaH+r6fHf4MXSGSG4HYHdwlYzY1IDSy/fZnX54PW/l
hiKDMuJxdk0X47AWDl4YS5Z1J1jBzkvpOcz96HJhwaUuDQzErumCqrI9AgMBAAGj
PzA9MA4GA1UdDwEB/wQEAwIFoDAdBgNVHSUEFjAUBggrBgEFBQcDAQYIKwYBBQUH
AwIwDAYDVR0TAQH/BAIwADANBgkqhkiG9w0BAQsFAAOCAQEAPI9hsFMLgZVLN1Sy
697uZxeEeOY4d6c+peUN5giefNaOqpNQiD/a+kD9lz3AEwFwxPOAeXx4mbGHHKqT
T1a8qP71tqm6WODPUR0cTFKN9J8Hy4/ViuUX+6qYXd/E+/4Erz61sVXleWIaxaAi
LgdlV7dFdjtIqSclaz5t6KmYysl5lzEGwJvPD21ax7CmomVGygBivUTShFAZVS2T
sXLgbuv2MI4tkP5jIefubMppva0blfetSY+/fEyt89n75IWaAm0tIGZmkmPxQwbV
sCQgivxWC9Vjp2Qmn+/SFp27HyEMwVEj9TxXGtO5YFzLQNKoYYmLwW9kUbOlJZDU
sKj51g==
-----END CERTIFICATE-----
"""

key="""-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAshZb/PVXn+dIHroNWcJIbPmQmNj4kAlMVfdilMyePMYwAAv9
aeuWnVYVLuvQRaXesW41WilxykduSRE5L7Fp7++pQ3XHZLgW/2M6CehY9+BusTfR
z4J/so6CRXR7MDcBBlvzH+J3B+Att1HsB6feFcHUC2mpbfjiNpftXcS4h+046Ho/
SSqXSgVhmheBKa1l5w1qNSoTQPo9pyuTI5+Ji2IotFdaHEGf0Lgn3mP7UQXizuC7
GxRjWh/q+nx3+DF0hkhuB2B3cJWM2NSA0sv32Z1+eD1v5YYigzLicXZNF+OwFg5e
GEuWdSdYwc5L6TnM/ehyYcGlLg0MxK7pgqqyPQIDAQABAoIBADQGyDTsT/8NCErB
u+i/E32SoyWkLWmW7dAnh4tFA+1pUNiSqCPriYLJhULB7YSLYrWfJsMCXJXlrFh4
SaafQ/2unFpy7B+GkGFn0arXUDaKQIxRbGAdFcVKUNCNqPd6+jerYSmtdWy9l114
92V9KypcB+CVq8PO8/dTBytfrzE2JZaMBTv59HF61oqjfP00oD/QRaalxpFmcIgc
GPc7gdgoL1MtL1FBz/qoU311qGj8ZQi7Yf25/MI00QdXNI4BN/Cb3f40htGIlDSl
aIeCTuOXqCZgMbtwH/ZQWY5ju1wYHU1gj+KM0BpnQoyWT5NJdKiZuNerjYT0wDsL
zqTtVUECgYEAzik1SxwHDSBZaQc89L3Kkl1dBLJHbtNHT/Pij3iefNXqtkLEUNjM
40qzkdknW2XymgDExOXeuB2bDeQ3oE6rV7hvVjveN8ZUuGbXJBQgvGtykVJEZvVM
2XQarV42+AUgU4ysr08nFJrEhXZ+p87Tr2LYBGJNWGGSdYKCh87MxfUCgYEA3SO+
axj1pSBLg0OXIyEe8wit49PeDZ2G1QKetSmsjsJUPCOx+E2hKjZgY4+3uCNGp8Ae
HkCaGtq6yRT7b/e/NQjX2tKPywr8loxV6mk3pf+AozTj4XIOuGgB03vzjJd9d12U
h2gj9rLllJYmbfuhxwqgTvVrughS1ih5UnoGRikCgYEAgdlWpc4rassbRZm3fPcl
ZfbEJbccYuNUITmdU3xHZp1dzhpTiBBlTCu62nwJ2/lkSjd9t/6IvzJ2fNNnbeLe
7MtP5OKkXkDfD55Gl4TN8Z9Dc+B7ENYj5zrHqraSrLid2cHa6jhShxnL+bvenlcY
4XjCUlCQIsCh/L2M9Xj9ZRkCgYBjyLEvmj+dlwj73g/gph1VBOGSIBPeiOpCS8BZ
dsiKUl24FVNE+6Jxbb/orPz1ddV39FSiyfu/ilsmSPV7/Iqm36qm7sQ7lmWLeR97
eqbFnJjrC/6Xx+Okiinox9GJ6wGOTweqYe94bhjyBx6oGhdRvRXBCzTk6MSYJgM4
mB8koQKBgQDB4yWtoj9b3yKLg/9efQ1JCkC2kNwZLHe11LFtLI8gLT1ZjBXnsair
B0keu+MT3bu8QBKRDvfaVFUG4+cLuL0k/2MGd/LME2v5mTPKdL2kMzFyYw282u2M
nKFJgBWQKZ0zkPJu+H/RcgJU/DAl9/zJ9+4azgg7eQ3rpvVK9vDA8w==
-----END RSA PRIVATE KEY-----
"""

endpoint="https://192.168.64.2:8443"

connector = KubernetesCliConnector(cert=cert, key=key, endpoint=endpoint)

docker_compose = """
apiVersion: v1
kind: Service
metadata:
  name: frontend
spec:
  ports:
  - port: 80
    protocol: TCP
    targetPort: 80
  selector:
    app: hello
    tier: frontend
  type: LoadBalancer
---
apiVersion: v1
kind: Service
metadata:
  name: hello
spec:
  ports:
  - port: 80
    protocol: TCP
    targetPort: http
  selector:
    app: hello
    tier: backend
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: hello
      tier: frontend
      track: stable
  template:
    metadata:
      labels:
        app: hello
        tier: frontend
        track: stable
    spec:
      containers:
      - image: gcr.io/google-samples/hello-frontend:1.0
        lifecycle:
          preStop:
            exec:
              command:
              - /usr/sbin/nginx
              - -s
              - quit
        name: nginx
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
spec:
  replicas: 1
  selector:
    matchLabels:
      app: hello
      tier: backend
      track: stable
  template:
    metadata:
      labels:
        app: hello
        tier: backend
        track: stable
    spec:
      containers:
      - image: gcr.io/google-samples/hello-go-gke:1.0
        name: hello
        ports:
        - containerPort: 80
          name: http
"""
stack_name = "8f4857f8-166c-11ea-b17a-784f43944dae"
env = []
files = []

connector.start(docker_compose=docker_compose, stack_name=stack_name, env=env, files=files)
#result = connector.stop(docker_compose=docker_compose, stack_name=stack_name, files=files)

print('The End')
