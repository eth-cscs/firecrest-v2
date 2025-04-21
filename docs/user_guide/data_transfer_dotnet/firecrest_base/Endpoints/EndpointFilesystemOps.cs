/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

using System.Net.Http.Headers;

namespace firecrest_base.Endpoints
{
    public class EndpointFilesystemOps : EndpointFilesystem
    {
        const int MAX_FILE_SIZE = 1048576; // 1 MB

        protected string URL { get; private set; }
        public EndpointFilesystemOps(string firecRESTurl, string system_name) : base(firecRESTurl, system_name)
        {
            URL = $"{EndpointURL}/ops";
        }

        // Upload single small file
        public async Task Upload(string sourceFile, string destinationFile)
        {
            // Extract file name and destination path
            string destinationFileName = destinationFile.Split('/').Last();
            string destinationPath = destinationFile[..(destinationFile.Length - destinationFileName.Length - 1)];
            // Set endpoint address and add query parameters 
            string url = $"{URL}/upload?path={Uri.EscapeDataString(destinationPath)}";

            // Check file size
            long fileSize = new FileInfo(sourceFile).Length;
            if (fileSize > MAX_FILE_SIZE)
                throw new Exception($"Size of uploading file {sourceFile} overcomes the limit of {MAX_FILE_SIZE} bytes.");

            // File data content
            using var form = new MultipartFormDataContent();
            byte[] fileBuffer = await File.ReadAllBytesAsync(sourceFile);
            var fileContentPart = new ByteArrayContent(fileBuffer);
            fileContentPart.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
            form.Add(fileContentPart, "file", destinationFileName);

            // Send request
            await RequestPost(url, form);
        }

        // Download single small file
        public async Task Download(string sourceFile, string destinationFile)
        {
            // Set endpoint address and add query parameters 
            string url = $"{URL}/download?path={Uri.EscapeDataString(sourceFile)}";

            // Send request
            var stream = await RequestGetStream(url);
            var fileStream = new FileStream(destinationFile, FileMode.OpenOrCreate, FileAccess.Write);
            await stream.CopyToAsync(fileStream);
            fileStream.Close();
            stream.Close();
        }
    }
}
