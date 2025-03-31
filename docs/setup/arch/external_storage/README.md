# Data Transfer

## Architecture
FirecREST enables users to upload and download large data packages of up to 5TB each, utilizing S3 buckets as a data buffer. 
Users requesting data uploads or downloads to the HPC infrastructure receive [presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html) to transfer data to or from the S3 storage.

Ownership of buckets and data remains with the FirecREST service account, but FirecREST creates one [bucket](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html#CoreConcepts) per user. Each file transferred (uploaded or downloaded) is stored in a unique identified [data object](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingObjects.html) into the user's bucket. Data objects within the buckets are retained for a configurable period, managed through S3's [lifecycle expiration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html) functionality. This expiration period, expressed in days, can be specified using the `bucket_lifecycle_configuration` parameter.

The S3 infrastructure can either be owned by the datacenter or AWS. All that's required is an valid service account to handle bucket creation and the generation of presigned URLs.

### External Data Upload

Uploading data from the extern of the HPC infrastructure requires the use of the [multipart upload protocol](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html). The data packet must be divided into parts, with the size limit of each part configurable via the `max_part_size parameter`. The specified value must be lower than [S3's maximum limit](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html) of 5GB per part.

The user needs to specify the name of the file to be uploaded, the destination path on the HPC cluster and the size of the file, which allows FirecREST to generate the set of presigned URLs for uploading each part. After the user completes the upload process, an already scheduled job transfers the data from the S3 bucket to its final destination on the HPC cluster, typically in dedicated storage.

The diagram below illustrates the sequence of calls required to correctly process an upload.

![external storage upload](../../../assets/img/external_storage_upload.svg)

1. The user calls API resource `transfer/upload` of endpoint `filesystem` with the parameters
    - `path`: destination of the file in the HPC cluster
    - `fileName`: destination name of the file
    - `fileSize`: size of the file to transfer expressed in bytes
2. FirecREST processes the request and, if valid, generates a dedicated bucket on S3 for the specific user. All further file transfers are conducted within this bucket
3. FirecREST schedules a job on the HPC cluster that waits for the completion of the upload in the S3 bucket
4. FirecREST returns the following information to the user
    - `maxPartSize`: the maximum size for parts
    - `partsUploadUrls`: one distinct upload URL per part
    - `completeUploadUrl`: the URL to complete the multipart upload in compliancy with S3 protocol
    - `transferJob`: information to track the data transfer job
5. The user uploads data on applying the [multipart protocol](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html) with [presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html). An S3 object, labeled with the file name and uniquely tagged by a UUID, is created within the user's bucket to receive the file parts and merge them into the final uploaded file. The protocol to be followed by users is implemented through the following steps:
    1. [Split the file into parts](https://docs.aws.amazon.com/AmazonS3/latest/userguide/tutorial-s3-mpu-additional-checksums.html#split-large-file-step2) of maximum size as specified
    2. Upload each part with the given URLs, collecting the returned [E-Tags](https://docs.aws.amazon.com/AmazonS3/latest/userguide/tutorial-s3-mpu-additional-checksums.html) for checkdata integrity verification
    3. Complete the upload with the given URL, providing the [list of the E-Tags](https://docs.aws.amazon.com/AmazonS3/latest/userguide/tutorial-s3-mpu-additional-checksums.html#complete-multipart-upload-step6)
6. The data transfer job detects the upload completion
7. The data transfer job downloads the incoming data from S3 to the destination specified by the user


### Download Data From Extern

Exporting large data packets from the HPC cluster to external systems begins with a user's request to download data. This triggers FirecREST to upload the data to an S3 bucket and then to provide a presigned URL to access the S3 object. Users must wait until the upload process within the HPC infrastructure is fully complete before accessing the data on S3.

To address any potential limitations, FirecREST schedules a job to transfer data to S3 using the multipart upload protocol. This process is entirely transparent to the user and ensures that the S3 object becomes accessible only once the transfer is successfully completed.

Once the presigned URL is provided by FirecREST, users can access the S3 bucket without any restrictions. The maximum file size allowed for a single download by S3 accommodates even large exported data files, in a single transfer.

The diagram below illustrates the sequence of calls required to correctly process a download.

![external storage upload](../../../assets/img/external_storage_download.svg)

1. The user calls API resource `transfer/download` of the `filesystem` endpoint providing the following parameter
    - `path`: source of the file in the HPC cluster
2. FirecREST processes the request and creates a dedicated bucket on S3 for the specific user (the same can be used for file transfer upload).
3. FirecREST schedules the data transfer job and responds to the user with the followng data:
    - `downloadUrl`: the presigned URL to access the S3 object containing the requested data
    - `transferJob`: information to track the data transfer job
4. The transfer job generates an S3 object within the user's designated bucket, labeled with the file name and uniquely tagged with a UUID. It automatically transfers data from the specified source into the bucket, utilizing the multipart upload protocol
5. Once the transfer is complete, the user can access the S3 object in the bucket until the expiration period ends

Although single-file download is an option, S3 supports [HTTP Range Request](https://www.rfc-editor.org/rfc/rfc9110.html#name-range-requests), which can be used to parallelly download chunks of a file stored in the S3 bucket.


