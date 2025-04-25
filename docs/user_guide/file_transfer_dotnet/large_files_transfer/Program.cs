/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

using firecrest_base.Types;
using firecrest_base.Endpoints;
using System.Security.Cryptography;

namespace large_files_transfer
{
    internal class Program
    {
        static void CreatePayload(string payloadFile, long payloadFileSizeMB)
        {
            using FileStream pld = File.OpenWrite(payloadFile);
            // Write file
            Random random = new Random();
            var buffer1MB = new byte[1024 * 1024];
            for (long i = 0; i < payloadFileSizeMB; i++)
            {
                random.NextBytes(buffer1MB);
                pld.Write(buffer1MB);
            }
            pld.Close();
        }

        static byte[] ComputePayloadHash(string payloadFile) {
            // Compute hash
            SHA256 sha256 = SHA256.Create();
            var inputFileStream = File.OpenRead(payloadFile);
            var hash = sha256.ComputeHash(inputFileStream);
            inputFileStream.Close();
            return hash;
        }

        static async Task Main()
        {
            string firecrestURL = "http://localhost:8000";
            string system_name = "cluster-slurm-api";
            string payloadFile = "payload.dat";
            string uploadFile = "/home/fireuser/test-upload.dat";
            string downloadFile = "payload-download.dat";

            try
            {
                Console.WriteLine("Large files transfer example");

                // Generate file to transfer
                CreatePayload(payloadFile, 1400); // size in MB
                var hash = ComputePayloadHash(payloadFile);
                string uploadHash = Convert.ToHexString(hash);
                Console.WriteLine($"Upload Hash {uploadHash}");

                // Instantiate Endpoints
                var efst = new EndpointFilesystemTransfer(firecrestURL, system_name);
                var ec = new EndpointCompute(firecrestURL, system_name);

                // FirecREST call to filesystem upload endpoint
                TransferJob? transferJob = await efst.Upload(payloadFile, uploadFile);

                // S3 upload complete, watch Transfer SchedulerJob status for internal data transfer
                Console.WriteLine("Upload to S3 complete");
                if (transferJob is not null) {
                    Console.WriteLine($"Monitoring transfer transferJob ID: {transferJob.jobId}");
                    string status = await ec.WaitForJobCompletion(transferJob.jobId);
                    Console.WriteLine(status);
                }
                Console.WriteLine("Upload complete");

                // Download the uploaded file
                await efst.Download(uploadFile, downloadFile);
                Console.WriteLine("Download complete");
                hash = ComputePayloadHash(downloadFile);
                string downloadHash = Convert.ToHexString(hash);
                Console.WriteLine($"Download Hash {downloadHash}");

                // Validate checksum
                if (uploadHash == downloadHash)
                    Console.WriteLine("SUCCESS");
                else
                    Console.WriteLine("FAILED");
            }
            catch (Exception ex)
            {
                Console.WriteLine(ex.ToString());
            }
            finally
            {
                // Cleanup
                if (File.Exists(payloadFile))
                    File.Delete(payloadFile);
                if (File.Exists(downloadFile))
                    File.Delete(downloadFile);
            }
        }
    }
}
