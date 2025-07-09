

# Configuration

The clients used to generate the user's JWT need to have a Client Scope that includes an audience mapper. The mapper should add an additional audience that needs to match with the DeiC sshca.CaConfig.ClientID setting. Otherwise the DeiC SSHCA will return error "aud mismatach".


# Usage

Generate a private and pub key pair:
```
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -C "your_email@example.com"
```

Optain a JWT for the Identity Provider
```
curl -X POST -d "grant_type=client_credentials&client_id=firecrest-test-client&client_secret=wZVHVIEd9dkJDh9hMKc6DTvkqXxnDttk" http://localhost:8080/auth/realms/kcrealm/protocol/openid-connect/token

```

Retreive the SSH Certificate

```

curl -X POST  --header "Content-Type: application/json"  --data '{"PublicKey": "<pub key>", "OTT": "<JWT-Token>"}' http://localhost:2280/demoCA/sign

```
