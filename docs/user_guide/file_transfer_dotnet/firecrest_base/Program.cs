/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

using firecrest_base.Endpoints;
using System.Text.Json;

namespace firecrest_base
{
    internal class Program
    {
        static void PrettyPrintJson(JsonElement json)
        {
            JsonSerializerOptions serializerOptions = new JsonSerializerOptions { WriteIndented = true };
            string formattedJson = JsonSerializer.Serialize(json, serializerOptions);
            Console.WriteLine(formattedJson);
        }

        static async Task Main()
        {
            string firecrestURL = "http://localhost:8000";
            try
            {
                Console.WriteLine("Authentication example");
                // FirecREST call to endpoint status/systems
                var es = new EndpointStatus(firecrestURL);
                // Show result
                JsonElement r = await es.Systems();
                PrettyPrintJson(r);
            }
            catch (Exception ex)
            {
                Console.WriteLine(ex.ToString());
            }
        }
    }
}
