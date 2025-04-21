/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

using System.Text.Json;

namespace firecrest_base.Endpoints
{
    public class EndpointStatus(string firecRESTurl) : Endpoint(firecRESTurl) 
    {
        public async Task<JsonElement> Systems()
        {
            return await RequestGet("status/systems");
        }
    }
}
