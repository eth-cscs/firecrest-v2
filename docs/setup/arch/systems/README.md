# FirecREST command execution

## The simplistic approach

The goal of FirecREST is to provide an HTTP interface to HPC, this means that the interface FirecREST presents to the users and applications must handle HTTP requests with according parameters, verbs, etc.

FirecREST receives these requests and translates them into HPC logic, and after the operations are done (ie, commands executed, data uploaded, etc) it returns an HTTP response that complies with the protocol used.

![f7t_simple](../../../assets/img/command_exec_simple.svg)

## Going deeper

The command execution from FirecREST API server to the HPC cluster is done **via SSH connection using HPC system users' credentials**.

This means that FirecREST can be installed in any platform or infrastructure (cloud provider, VM, local system) with SSH access to the target system(s) configured. It doesn't need to be installed in the same VPN or VLAN of the system.

!!! info
    FirecREST doesn't execute commands as `root` user or using `sudo` commands. All commands are executed on behalf of the users using the users' credential.

## JWT to SSH Delegation

To answer to the question on "how the SSH credentials are obtained or created", FirecREST provides an integration with JSON Web Tokens used to authenticate agains the API.

FirecREST uses the `username` or `preferred_username` claim from the JWT access token created by the Identity Provider (IdP) when the user or application [authenticated to use the API](../auth/README.md).

!!! info
    This `username` value on the token must be a valid username on the HPC system, otherwise the SSH credential created on its behalf won't be allowed in the system.

The JWT signature is verified using the Identity Provider (IdP) public key, and then the token time validity is checked. If both are successful, the `username` is extracted and a SSH key is created for the user if there isn't an active connection to the cluster.

### Obtaining SSH credentials on behalf of the user

FirecREST provides an abstraction to allow different ways of getting SSH credentials for the user. Currently, there are the 2 options available:

[](){#f7t-ssh-service}

1. Using an "SSH Service"

    If the HPC center has an API or web service that translates a JWT into an SSH credential, you can connect FirecREST to this service.

    ![f7t_ssh_service](../../../assets/img/command_exec_sshservice.svg)

    In this case, the user sends the JWT to FirecREST and it is forwarded to the SSH Service. Therefore, the IdP that generates JWT must be trusted by both FirecREST and the SSH Service.

    Once the SSH credential is created, FirecREST uses the SSH credential to execute commands.

    The benefit of this approach is that SSH credentials creation and validation is managed within the specific groups.

2. Using static SSH credentials

    Additionally, FirecREST provides a way to map user identities in the JWT with SSH credentials by using the [firecrest-config.yaml](../../conf/README.md).

    ![f7t_ssh_service](../../../assets/img/command_exec_nosshsvc.svg)

    SSH credentials or the users should be managed as secrets and should be updated by the administrator of the FirecREST deployment if they change.

## SSH Configuration in target systems

!!! info
    All these configurations are optional, but strongly suggested to increase security (remember that we are allowing machines to machine communication via SSH, we don't want an SSH DoS!) and provide high througput regime via API

It is recommended to set a specific `Match` section on the [Open SSHD configuration](https://man.openbsd.org/OpenBSD-current/man5/sshd_config.5#Match) for requests from FirecREST:

!!! example "Login node SSHd Config"
    ```bash
    $ cat /etc/ssh/sshd_config
    (...)
    # To accept FirecREST host
    Match Address {IP_ADDR_or_RANGE}
        TrustedUserCAKeys /path/to/ssh/key.pub
        PermitRootLogin no
        DenyGroups root bin admin sys
        MaxAuthTries 1
        AllowTcpForwarding no
        MaxSessions 2500
    ```

### SSH Configuration details

!!! Note
    You can follow this [link](https://man7.org/linux/man-pages/man5/sshd_config.5.html) to have a more complete understanding on SSH configuration used below

- `Match Address`: points the IP address (or range) from where FirecREST server connects to the cluster. This way, this `Match` block only process SSH connections from FirecREST.

- `TrustedUserCAKeys`: in case of using an [SSH Service][f7t-ssh-service] this option points to the path where the public key of the Certificate Authority that signs SSH credentials is stored.

- `DenyGroups`: to avoid these special permission groups from executing commands via FirecREST

- `MaxSessions`: sessions are a result of (SSH connections x Commands executed). The default value is `10`, but to allow [high throughput regime][f7t-ssh-pool] on commands execution via FirecREST, set this value to a higher number (recommended `9999` which is the max allowed value).

[](){#f7t-ssh-pool}
## How to enable High Throughput Regime via FirecREST

To enable high throughput operations on HPC via an API, the FirecREST team has set the **SSH connection pool**.

Instead of using one SSH connection+channel per command, this approach re-uses an SSH connection to execute several commands on a row.​

Each connection in the pool is closed after a time of inactivity, leaving it available for the next user.

![f7t_ssh_pool](../../../assets/img/command_exec_sshpool.svg)

!!! Note
    Using this setup, stress testing has proven that 500 clients can produce ~195 request per second with a latency of 900 ms, and an error rate of 0.04%​ (always depending of the infrastructure, filesystems, network latency, etc)
