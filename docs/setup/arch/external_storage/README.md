# Data Transfer

## Architecture
FirecREST enables users to upload and download large data packages of up to 5TB each, utilizing S3 buckets as a data buffer. Users requesting data uploads or downloads to the HPC infrastructure receive presigned URLs to transfer data to or from the S3 storage.

Ownership of buckets and data remains with the FirecREST service account, and buckets are created based on user requests. Data objects within the buckets are retained for a configurable period, managed through S3's lifecycle expiration functionality. This expiration period, expressed in days, can be specified using the `bucket_lifecycle_configuration` parameter.

The S3 infrastructure can either be owned by the datacenter or AWS. All that's required is an valid service account to handle bucket creation and the generation of presigned URLs.

### External Data Upload

Uploading data from the extern of the HPC infrastructure requires the use of the multipart upload protocol. The data packet must be divided into parts, with the size limit of each part configurable via the `max_part_size parameter`. The specified value must be lower than S3's maximum limit of 5GB per part.

The user needs to specify the name of the file to be uploaded, the destination path on the HPC cluster and the size of the file, which allows FirecREST to generate the set of presigned URLs for uploading each part. After the user completes the upload process, an already scheduled job transfers the data from the S3 bucket to its final destination on the HPC cluster, typically in dedicated storage.

The diagram below illustrates the sequence of calls required to correctly process an upload.

![external storage upload](../../../assets/img/external_storage_upload.svg)

1. The user calls API resource `transfer/upload` of endpoint `filesystem` with the parameters
    - `path`: destination of the file in the HPC cluster
    - `fileName`: destination name of the file
    - `fileSize`: size of the file to transfer expressed in bytes
2. FirecREST receives the request and, if valid, creates a bucket on S3
3. FirecREST schedules a job on the HPC cluster that waits for the completion of the upload in the S3 bucket
4. FirecREST returns the following information to the user
    - `maxPartSize`: the maximum size for parts
    - `partsUploadUrls`: one distinct upload URL per part
    - `completeUploadUrl`: the URL to complete the multipart upload in compliancy with S3 protocol
    - `transferJob`: information to track the data transfer job
5. The user uploads data on
    1. split the file into parts of maximum size as specified
    2. upload each part with the given URLs, collecting the returning E-Tags
    3. complete the upload with the given URL
6. The data transfer job detects the upload completion
7. the data transfer job downloads the incoming data from S3 to the destination specified by the user


### Download Data From Extern

Exporting large data packets from the HPC cluster to external systems begins with a user's request to download data. This triggers FirecREST to upload the data to an S3 bucket and then to provide a presigned URL to access the S3 object. Users must wait until the upload process within the HPC infrastructure is fully complete before accessing the data on S3.

To address any potential limitations, FirecREST schedules a job to transfer data to S3 using the multipart upload protocol. This process is entirely transparent to the user and ensures that the S3 object becomes accessible only once the transfer is successfully completed.

Once the presigned URL is provided by FirecREST, users can access the S3 bucket without any restrictions. The maximum file size allowed for a single download by S3 accommodates even large exported data files, in a single transfer.

The diagram below illustrates the sequence of calls required to correctly process a download.

![external storage upload](../../../assets/img/external_storage_download.svg)

1. The user calls API resource `transfer/download` of the `filesystem` endpoint providing the following parameter
    - `path`: source of the file in the HPC cluster
2. FirecREST processes the request and creates the S3 bucket
3. FirecREST schedules the data transfer job and responds to the user with the followng data:
    - `downloadUrl`: the presigned URL to access the S3 object containing the requested data
    - `transferJob`: information to track the data transfer job
4. The transfer job creates the S3 object and transfers the data from the specified source into it
5. Once the transfer is complete, the user can access the S3 object in the bucket until the expiration period ends


## API endpoints

### Upload

### Download
