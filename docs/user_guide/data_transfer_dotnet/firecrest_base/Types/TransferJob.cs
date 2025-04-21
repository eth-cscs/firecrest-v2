/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

namespace firecrest_base.Types
{
    public class TransferJob
    {
        public int jobId { get; set; }
        public string? system { get; set; }
        public string? workingDirectory { get; set; }
        public Dictionary<string, string>? logs { get; set; }
    }
}
