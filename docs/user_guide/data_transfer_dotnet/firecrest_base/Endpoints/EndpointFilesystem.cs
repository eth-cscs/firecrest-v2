/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

namespace firecrest_base.Endpoints
{
    public class EndpointFilesystem(string firecRESTurl, string system_name) : Endpoint(firecRESTurl) 
    {
        protected string EndpointURL { get; private set; } = $"filesystem/{system_name}";
        protected string SystemName { get; private set; } = system_name;
    }
}
