/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

using firecrest_base.Endpoints;
using System.Security.Cryptography;

namespace small_files_transfer
{
    internal class Program
    {
        static void CreatePayload(string payloadFile, long payloadFileSizeKB)
        {
            using FileStream pld = File.OpenWrite(payloadFile);
            // Write file
            Random random = new Random();
            var buffer1KB = new byte[1024];
            for (long i = 0; i < payloadFileSizeKB; i++)
            {
                random.NextBytes(buffer1KB);
                pld.Write(buffer1KB);
            }
            pld.Close();
        }

        static byte[] ComputePayloadHash(string payloadFile)
        {
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
            string payloadFile = "payload-small.dat";
            string uploadFile = "/home/fireuser/test-upload-small.dat";
            string downloadFile = "payload-small-download.dat";

            try
            {
                Console.WriteLine("Small files transfer example");

                // Generate file to transfer
                CreatePayload(payloadFile, 5); // size in KB
                var hash = ComputePayloadHash(payloadFile);
                string uploadHash = Convert.ToHexString(hash);
                Console.WriteLine($"Upload Hash {uploadHash}");

                // Instantiate Endpoints
                var efso = new EndpointFilesystemOps(firecrestURL, system_name);

                // FirecREST call to filesystem upload endpoint
                await efso.Upload(payloadFile, uploadFile);
                Console.WriteLine("Upload complete");

                // Download the uploaded file
                await efso.Download(uploadFile, downloadFile);
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
