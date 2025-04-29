/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

using firecrest_base.Types;
using System.Text.Json;
using System.Net;

namespace firecrest_base.Endpoints
{
    public class EndpointCompute (string firecRESTurl, string system_name) : Endpoint (firecRESTurl)
    {
        protected string EndpointURL { get; private set; } = $"compute/{system_name}";
        protected string SystemName { get; private set; } = system_name;

        public async Task<SchedulerJob> GetJob(int jobId)
        {
            var response = await RequestGet($"{EndpointURL}/jobs/{jobId}");
            SchedulerJobs? tmp = response.Deserialize<SchedulerJobs>();

            if (tmp is null || tmp.jobs.Length == 0)
                throw new Exception("job not found");
            return tmp.jobs[0];
        }

        public async Task<string> WaitForJobCompletion(int jobId, int timeout=60)
        {
            // Wait for transfer job to complete the file copy on S3
            string end_state="";
            int counter=timeout;
            while(end_state == "")
            {
                SchedulerJob? job;
                try {
                    // Since transfer takes time, the access token can expire in the meanwhile.
                    if (IsTokenExpired())
                        await RefreshToken();
                    job = await GetJob(jobId);
                    //Console.WriteLine($"Scheduler job: {job.jobId} {job.status.state}");
                    Console.Write(".");
                    if (job is null)
                        throw new Exception("Transfer job not started.");
                    if (job.status is null)
                        throw new Exception("Transfer job status not readable.");

                    if (job.status.state != "RUNNING" && job.status.state != "PENDING")
                        end_state = job.status.state ?? "";
                }
                catch (HttpRequestException ex) when (ex.StatusCode == HttpStatusCode.NotFound)
                {
                    if (--counter == 0)
                        throw;
                }
                await Task.Delay(1000);
            }

            // Job completed
            if (end_state != "COMPLETED")
                throw new Exception($"Transfer job failed with status {end_state}");
            return end_state;
        }
    }
}
