# Health checks

Internally, FirecREST performs a periodic **health check** of all the pieces of infrastructure that needs to work correctly.

These periodic tests not only provide the users with updated information about the current status of the HPC Center infra, but help FirecREST to run faster and more efficiently.

![f7t_health_checks](../../../assets/img/health_checks.svg)

As you can see in the figure above, when enabled the periodic health check will update the status of

1. HPC cluster connectivity (via SSH)
2. Workload manager and scheduler (via SSH or API, depending the service)
3. Filesystem availability (read only)
4. Object storage availabitity (S3 interface is reachable or not)

## Status reports

When consulting the API endpoint `/status/systems` you can see the status of health checks on the response JSON. The filed `servicesHealth` is composed of a list of `serviceTypes` as listed above.

The common format includes:

- `serviceType`: can be (1) `ssh`, (2) `scheduler`, (3) `filesystem`, and (4) `s3`.
- `lastChecked`: timestamp of the last time the periodic test was performed
- `latency`: is used to establish if the service is healthy or not (depends on the configuration of FirecREST)
- `healthy`: `true` or `false`
- `message`: in case of error, it describes why the probe failed

??? example "Health check response for `serviceType: ssh`"
    ```json
    {
        "systems":[
            {
                "name": "system01",
                (...)
                "servicesHealth": [
                    (...)
                    {
                        "serviceType":"ssh",
                        "lastChecked":"2025-04-02T07:48:48.367139Z",
                        "latency":0.4212830066680908,
                        "healthy":true,
                        "message":null
                    },
                    (...)
                ]
            },
            {
                "name": "system02",
                (...)
                {
                    "serviceType": "ssh",
                    "lastChecked": "2025-04-02T07:48:49.082887Z",
                    "latency": 1.1373629570007324,
                    "healthy": false,
                    "message": "Too many authentication failures"
                },
            }
        ]
    }
    ```

??? example "Health check response for `serviceType: scheduler`"
    ```json
    {
        "systems":[
            {
                "name": "system01",
                (...)
                "servicesHealth": [
                    {
                        "serviceType":"scheduler",
                        "lastChecked":"2025-04-01T00:01:00.000000Z",
                        "latency":1.1002883911132812,
                        "healthy":true,
                        "message":null,
                        "nodes": {
                            "available":130,
                            "total":143
                        }
                    },
                ]
            },
            {
                "name": "system02",
                (...)
                "servicesHealth": [
                    {
                        {
                            "serviceType":"scheduler",
                            "lastChecked":"2025-04-01T00:01:00.000000Z",
                            "latency":0.02857375144958496,
                            "healthy":false,
                            "message":"ClientConnectorError: Cannot connect to host",
                            "nodes":null
                        }
                    }
                ]
            }
        ]
    }
    ```

??? example "Health check response for `serviceType: filesystem`"
    ```json
    {
        "systems":[
            {
                "name": "system01",
                (...)
                "servicesHealth": [
                    {
                        "serviceType":"filesystem",
                        "lastChecked":"2025-04-01T00:01:00.000000Z",
                        "latency":1.3535213470458984,
                        "healthy":true,
                        "message":null,
                        "path":"/path/to/filesystem01"
                    },
                    {
                        "serviceType": "filesystem",
                        "lastChecked":"2025-04-01T00:01:00.000000Z",
                        "latency":0.9655811786651611,
                        "healthy":false,
                        "message":"Too many authentication failures",
                        "path":"/path/to/filesystem02"
                    }
                ]
            }
        ]
    }
    ```

??? example "Health check response for `serviceType: s3`"
    ```json
    {
        "systems":[
            {
                "name": "system01",
                (...)
                "servicesHealth": [
                    {
                        "serviceType": "s3",
                        "lastChecked":"2025-04-01T00:01:00.000000Z",
                        "latency": 0.22784161567687988,
                        "healthy": true,
                        "message": null
                    }
                ]
            }
        ]
    }
    ```

## Improving command execution

Health checks not only provide information about the status of the underlying infrastructure of the HPC center; they enable FirecREST to predict that the command executed in the cluster has a very high probability of being executed as expected.

When enabled, FirecREST will prevent execute commands on unhealthy services

!!! example "API call to an unhealthy endpoint"
    ```bash
    $ curl filesystem/system02/ops/ls?path=/path/to/filesystem02
    {
        "errorType": "error",
        "message": "The ssh service for the requested system (zinal) is unhealthy.",
        "data": null,
        "user": "firecr01"
    }
    ```

