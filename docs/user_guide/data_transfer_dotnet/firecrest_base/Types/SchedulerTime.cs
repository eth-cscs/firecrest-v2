/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

namespace firecrest_base.Types
{
    public class SchedulerTime
    {
        public long? elapsed {  get; set; }
        public long? start  {  get; set; }
        public long? end {  get; set; }
        public long? suspended {  get; set; }
        public long? limit {  get; set; }
    }
}
