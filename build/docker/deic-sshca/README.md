

# Configuration

The clients used to generate the user's JWT need to have a Client Scope that includes an audience mapper. The mapper should add an additional audience that needs to match with the DeiC sshca.CaConfig.ClientID setting. Otherwise the DeiC SSHCA will return error "aud mismatach".

To username set as principal in the generated certificate needs to be set in the JWT sub claim. The Identity Provider (e.g. Keycloaclk) needs to be configured accordingly.


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

# TODO

## Fix Certificate Validity
By default the certificate validity is 1m, for some reaons this often result in SSHD rejecting the certificate.
Extending the validity to 5m fixes the issue. However the certificate TTL configuration is ignored for some reason.

Fix proposed: https://github.com/wayf-dk/sshca/pull/2


## Remove custom sshca.go impl
Once the above fixes are implemented the custom sshca.go file should be removed.
