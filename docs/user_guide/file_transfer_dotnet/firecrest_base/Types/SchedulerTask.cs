/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

namespace firecrest_base.Types
{
    public class SchedulerTask
    {
        public string? id { get; set; }
        public string? name { get; set; }
        public SchedulerJobStatus? status { get; set; }
        public SchedulerTime? time { get; set; }
    }
}
