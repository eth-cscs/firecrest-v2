/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

namespace firecrest_base.Types
{
    public class TransferDirectivesS3
    {
        public string? transfer_method { get; set; }
        public string[]? parts_upload_urls { get; set; }
        public string? complete_upload_url { get; set; }
        public long max_part_size { get; set; }
    }
}

