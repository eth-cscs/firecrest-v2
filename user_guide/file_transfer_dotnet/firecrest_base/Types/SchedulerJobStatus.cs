/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

namespace firecrest_base.Types
{
    public class SchedulerJobStatus
    {        
        public string? state { get; set; }
        public string? stateReason {  get; set; }
        public int exitCode { get; set; }
        public int interruptSignal { get; set; }
    }
}
