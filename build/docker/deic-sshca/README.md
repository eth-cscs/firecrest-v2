

# Configuration

The clients used to generate the user's JWT need to have a Client Scope that includes an audience mapper. The mapper should add an additional audience that needs to match with the DeiC sshca.CaConfig.ClientID setting. Otherwise the DeiC SSHCA will return error "aud mismatach".