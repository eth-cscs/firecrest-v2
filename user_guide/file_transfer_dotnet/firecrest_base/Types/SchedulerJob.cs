/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

namespace firecrest_base.Types
{
    public class SchedulerJob
    {
        public int jobId { get; set; }
        public string? name { get; set; }
        public SchedulerJobStatus? status { get; set; }
        public SchedulerTask[]? tasks { get; set; }

        public string? account { get; set; }
        public int allocationNodes { get; set; }
        public string? cluster { get; set; }
        public string? group { get; set; }
        public string? nodes { get; set; }
        public string? partition { get; set; }
        public int priority { get; set; }
        public string? killRequestUser { get; set; }
        public string? user { get; set; }
        public string? workingDirectory { get; set; }
    }
}
