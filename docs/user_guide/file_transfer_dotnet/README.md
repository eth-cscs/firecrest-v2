# FirecREST File Transfer with C# .NET
## General description
The .NET solution file (`data_transfer_dotnet.sln`) is available by cloning this repository and accessing to the path [docs/user_guide/file_transfer_dotnet](.).

!!! example "Getting the .NET solution."
    ```
    git clone https://github.com/eth-cscs/firecrest-v2.git
    cd firecrest-v2/docs/user_guide/file_transfer_dotnet
    ```

This .NET solution provides examples demonstrating how to connect to FirecREST and transfer files using C# via different API endpoints. The implementation follows a fully `async` approach.

The Examples do not requires parameters. You may be able to build them and run the generated executable. All of them, by default, target the [Docker-Compose demo environment](../../getting_started/README.md#trying-firecrest-in-a-containerised-environment).

## Environment and packages
The examples are written in C# for .NET 8.0. 
To compile and run the examples an extra package is requested: <i>Microsoft.IdentityModel.JsonWebTokens version 8.8.0</i>

You can install it using your preferred method or one of the following commands:

`dotnet add package Microsoft.IdentityModel.JsonWebTokens --version 8.8.0`

`NuGet\Install-Package Microsoft.IdentityModel.JsonWebTokens -Version 8.8.0`

## Unix build script
This script is designed to automatically adapt the project files, build the source code, and place the resulting executables into the examples_bin directory. Additionally, it copies the .credentials_demo file, as outlined in Example 1 below.

If you are working with .NET on a Unix-like system (Linux or MacOS) just run the `unix_build.sh` script.
It is designed to automatically adapt the project files, build the source code, and place the resulting executables into the examples_bin directory. Additionally, it copies the `.credentials_demo` file, as outlined in [Example 1](#example-1-base-authentication) below.

## Solution structure
The solution contains three projects. The `firecrest_base` project includes all the necessary classes for accessing FirecREST, managing authentication, and transferring files.

Note that the projects `large_files_transfer` and `small_file_transfer` depends on the `firecrest_base` project. It is therefore recommended to build the `firecrest_base` project before to build the other two examples.

The `firecrest_base` project is divided into the following directories.
### Access
This directory contains classes for handling authentication, such as [AccessToken](firecrest_base/Access/AccessToken.cs) and [AccessTokenRequest](firecrest_base/Access/AccessTokenRequest.cs).
### Types
This directory includes a collection of classes representing structured data types, used for serializing and deserializing requests and responses exchanged with FirecREST.
### Endpoints
This directory holds all the classes required to interact with FirecREST API endpoints, designed following an inheritance-based architecture. The following class diagram represents the structure of them.

![f7t_authn_basic](../../assets/img/dot_net_class_diagram.svg)

## Examples
### Example 1: base authentication 
The [Program.cs](firecrest_base/Program.cs) in the `firecrest_base` project demonstrates the simplest connection to FirecREST. It initializes the [EndpointStatus](firecrest_base/Endpoints/EndpointStatus.cs) class and retrieves the Systems API result.

!!! example "`EndpointStatus` class example call."
    ```cs
    // FirecREST call to endpoint status/systems
    var es = new EndpointStatus(firecrestURL);
    // Show result
    JsonElement r = await es.Systems();
    ```

The [EndpointStatus](firecrest_base/Endpoints/EndpointStatus.cs) object authenticates access using the `AccessTokenRequest` object, which is managed by the abstract class [Endpoint](firecrest_base/Endpoints/Endpoint.cs).

<b>Note that the</b> `AccessTokenRequest` <b>class requires a</b> `.credentials` <b>file to be located in the same directory as the executable.</b>

An example `.credentials_demo` file, configured for accessing the Docker demo environment, is available in the examples' main directory under the endpoint status folder. The file contains the following JSON structure:

!!! example "Inner structure of `.credentials` file."
    ```json
    {
        "Url": "http://localhost:8080/auth/realms/kcrealm/protocol/openid-connect/token",
        "ClientID": "firecrest-test-client",
        "ClientSecret": "wxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxk"
    }
    ```

<b>Tip</b>: if you are running the solution using Visual Studio on Windows, post-build events have been configured to automatically copy the `.credentials_demo` file to the build directory of each project as `.credentials`.

### Example 2: large files transfer
The [Program.cs](large_files_transfer/Program.cs) in the `large_files_transfer`) project generates a random content file with an arbitrary customizable by the function:

!!! example "Payload file creation."
    ```cs
    CreatePayload(payloadFile, 2400); // size in MB
    ```

After generating the file, the example uploads it using the [EndpointFilesystemTransfer](firecrest_base/Endpoints/EndpointFilesystemTransfer.cs) class, which implements the [AWS multipart upload protocol](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html). It then waits for the scheduled transfer job to complete by utilizing the `WaitForJobCompletion` method from the [EndpointStatus](firecrest_base/Endpoints/EndpointStatus.cs) class.

Once the upload is finished, the example downloads the same file, saving it locally under a new name. To ensure the data transfer was successful, checksums of the original and downloaded files are calculated and compared.

### Example 3: small files transfer
The [Program.cs](small_files_transfer/Program.cs) in the `small_files_transfer` project generates a random content file with an arbitrary customizable size using a similar function as implemented in Example 2. In this case, the size is expressed in kilobytes (KB). Please note that the maximum file size allowed for direct upload and download using the `ops` endpoint is 1MB. For larger files, the `transfer` endpoint, discussed in example 2, must be used.

!!! example "Payload file creation."
    ```cs
    CreatePayload(payloadFile, 5); // size in KB
    ```

The example utilizes the [EndpointFilesystemOps](firecrest_base/Endpoints/EndpointFilesystemOps.cs) class to upload a file on the specified path.

Once the upload is finished, the example downloads the same file, saving it locally under a new name. To ensure the data transfer was successful, checksums of the original and downloaded files are calculated and compared.

