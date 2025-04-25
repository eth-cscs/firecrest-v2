/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

using firecrest_base.Types;
using System.Text.Json;

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

        public async Task<string> WaitForJobCompletion(int jobId)
        {
            // Wait for transfer job to complete the file copy on S3
            SchedulerJob? job;
            do
            {
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
                await Task.Delay(1000);
            }
            while (job.status.state == "RUNNING" || job.status.state == "PENDING");
            // Job completed
            if (job.status.state != "COMPLETED")
                throw new Exception($"Transfer job failed with sttus {job.status.state}");
            return job.status.state;
        }
    }
}
