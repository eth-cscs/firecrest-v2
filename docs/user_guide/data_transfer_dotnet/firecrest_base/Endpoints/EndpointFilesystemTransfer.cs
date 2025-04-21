/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

using firecrest_base.Types;
using System.Text;
using System.Text.Json;
using System.Xml;

namespace firecrest_base.Endpoints
{
    public class EndpointFilesystemTransfer : EndpointFilesystem
    {
        protected string URL { get; private set; }

        // Class attributes names are case sensitive and shall match with response fields
        protected class MultipartUploadData
        {
            public string []? partsUploadUrls { get; set; }
            public string? completeUploadUrl { get; set; }
            public long maxPartSize { get; set; }
            public TransferJob? transferJob { get; set; }
        };

        // Class attributes names are case sensitive and shall match with response fields
        protected class DownloadData
        {
            public string? downloadUrl { get; set; }
            public TransferJob? transferJob { get; set; }
        }

        public EndpointFilesystemTransfer(string firecRESTurl, string system_name) : base(firecRESTurl, system_name)
        {
            URL = $"{EndpointURL}/transfer";
        }

        /* ------------------------------------------------------------------------------------------------------------- */

        public async Task<TransferJob?> Upload(string sourceFile, string destinationFile, string account="csstaff")
        {
            // Set endpoint address 
            string url = $"{URL}/upload";
            // Destination file settings
            string destinationFileName = destinationFile.Split('/').Last();
            string destinationPath = destinationFile[..(destinationFile.Length - destinationFileName.Length - 1)];
            // Get file size
            long fileSize = new FileInfo(sourceFile).Length;
            Console.WriteLine($"Uploading file size: {fileSize}");

            // Prepare request
            Dictionary<string, string> formData = new()
            {
                { "path",     destinationPath },
                { "fileName", destinationFileName },
                { "account",  account },
                { "fileSize", $"{fileSize}" }
            };
            string response = await RequestPost(url, formData);
            MultipartUploadData? mpu = JsonSerializer.Deserialize<MultipartUploadData>(response);

            if (mpu != null)
            {
                // Check memory boundaries
                if (mpu.maxPartSize > int.MaxValue)
                    throw new Exception($"Part size [{mpu.maxPartSize} bytes] exceeds memory limit");
                int maxPartSize = (int)mpu.maxPartSize;

                // Got Multipart transfer presigned URLs, proceed with upload
                HttpClient client = new();
                Dictionary<int, string> eTags = [];
                Dictionary<int, string> failedPartsList = [];
                FileStream fileStream = new(sourceFile, FileMode.Open);
                byte[] dataPartBuffer = new byte[maxPartSize];
                int partIndex = 1;

                // Check for URLs in the response
                if (mpu.partsUploadUrls is null || mpu.completeUploadUrl is null )
                    throw new Exception("Missing URLs in Multipart upload response");

                // Try to upload parts, sequentially
                Console.WriteLine($"Uploading {mpu.partsUploadUrls.Length} parts");
                foreach (string partUrl in mpu.partsUploadUrls)
                {
                    try
                    {
                        await UploadPart(maxPartSize, client, eTags, fileStream, dataPartBuffer, partIndex, partUrl);
                    }
                    catch (Exception ex)
                    {
                        // Part upload failed, append it to the retry list
                        Console.WriteLine(ex.ToString());
                        failedPartsList.Add(partIndex, partUrl);
                    }
                    // Next part
                    partIndex++;
                }
                fileStream.Close();

                // Check completion
                if (failedPartsList.Count > 0)
                    throw new Exception("Upload failed");

                // Upload of parts succeeded, complete Multipart protocol.
                await CompleteMultipartUpload(mpu.completeUploadUrl, client, eTags);
                return mpu.transferJob;
            }
            return null;
        }

        private async Task UploadPart(int maxPartSize, HttpClient client, Dictionary<int, string> eTags, FileStream fileStream, byte[] dataPartBuffer, int partIndex, string partUrl)
        {
            // Read part's data from file
            int bufferLength = await fileStream.ReadAsync(dataPartBuffer, 0, maxPartSize); // file size!!!
            var partData = new ByteArrayContent(dataPartBuffer, 0, bufferLength);
            // Upload part's data
            HttpResponseMessage s3response = await client.PutAsync(partUrl, partData);
            s3response.EnsureSuccessStatusCode();
            // Get ETag
            s3response.Headers.GetValues("ETag");
            if (s3response.Headers.TryGetValues("ETag", out IEnumerable<string>? etag))
                eTags.Add(partIndex, etag.First());
        }

        private static async Task CompleteMultipartUpload(string url, HttpClient client, Dictionary<int, string> eTags)
        {
            // Parts upload completed, prepare ETags list
            XmlDocument eTagsReportList = new XmlDocument();
            var xmlRoot = eTagsReportList.CreateElement("CompleteMultipartUpload");
            xmlRoot.SetAttribute("xmlns", "http://s3.amazonaws.com/doc/2006-03-01/");
            eTagsReportList.AppendChild(xmlRoot);
            // Append ETags
            for (int i = 1; i <= eTags.Count; i++)
            {
                XmlElement partElement = eTagsReportList.CreateElement("Part");
                XmlElement partNumberElement = eTagsReportList.CreateElement("PartNumber");
                XmlElement ETagElement = eTagsReportList.CreateElement("ETag");

                partNumberElement.InnerText = $"{i}";
                ETagElement.InnerText = eTags[i].ToString();

                partElement.AppendChild(partNumberElement);
                partElement.AppendChild(ETagElement);
                xmlRoot.AppendChild(partElement);
            }
            // Close Multipart protocol
            Console.WriteLine("Completing Multipart transfer");
            var content = new StringContent(eTagsReportList.OuterXml, Encoding.UTF8, "application/xml");
            HttpResponseMessage response = await client.PostAsync(url, content);
            response.EnsureSuccessStatusCode();
        }

        /* ------------------------------------------------------------------------------------------------------------- */

        public async Task Download(string sourceFile, string destinationFile, string account = "csstaff")
        {
            string url = $"{URL}/download";

            // Prepare request data
            Dictionary<string, string> formData = new()
            {
                { "sourcePath", sourceFile },
                { "account",  account }
            };

            // Call API endpoint
            string response = await RequestPost(url, formData);
            DownloadData? downloadData = (JsonSerializer.Deserialize<DownloadData>(response) ?? throw new Exception("Download failed: null repsonse received")) ?? throw new Exception("Download API call failed");
            
            // Get Transfer job
            TransferJob? transferJob = downloadData.transferJob ?? throw new Exception("Null transfer job received");

            // Wait for transfer job to complete the file copy on S3
            Console.WriteLine($"Monitoring transfer transferJob ID: {transferJob.jobId}");
            EndpointCompute ec = new EndpointCompute(FirecRESTurl, SystemName);
            string status = await ec.WaitForJobCompletion(transferJob.jobId);
            Console.WriteLine(status);

            // Got presigned URL, proceed with download
            Console.WriteLine("Downloading the file from S3");
            using HttpClient client = new();
            using HttpResponseMessage s3Response = await client.GetAsync(downloadData.downloadUrl, HttpCompletionOption.ResponseHeadersRead);
            using Stream downloadStream = await s3Response.Content.ReadAsStreamAsync();
            using FileStream fileStream = File.OpenWrite(destinationFile);
            {
                await downloadStream.CopyToAsync(fileStream);
            }            
        }
    }
}
