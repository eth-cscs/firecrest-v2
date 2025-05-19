/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

using System.Text;
using System.Net.Http.Headers;
using System.Text.Json;
using firecrest_base.Access;

namespace firecrest_base.Endpoints
{
    public abstract class Endpoint (string firecRESTurl)
    {
        protected string FirecRESTurl { get; private set; } = firecRESTurl;
        protected AccessToken? AccessToken { get; private set; } = null;
        protected AccessTokenRequest AccessTokenRequest { get; private set; } = new AccessTokenRequest();

        protected async Task<HttpClient> InitClient()
        {
            if (AccessToken is null)
                await RefreshToken();

            HttpClient client = new HttpClient();
            client.DefaultRequestHeaders.Add("Accept", "*/*");
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", AccessToken.Token);
            return client;
        }

        public async Task RefreshToken()
        {
            AccessToken = await AccessTokenRequest.get() ?? throw new Exception("Null access token");
        }

        public bool IsTokenExpired()
        {
            if (AccessToken is null)
                return true;
            return AccessToken.HasExpired();
        }

        protected async Task<JsonElement> RequestGet(string resource)
        {
            HttpClient client = await InitClient();
            var url = $"{FirecRESTurl}/{resource}";

            HttpResponseMessage response = await client.GetAsync(url);
            response.EnsureSuccessStatusCode();

            // Decode response
            var body = await response.Content.ReadAsStringAsync();
            return JsonDocument.Parse(body).RootElement;
        }

        protected async Task<Stream> RequestGetStream(string resource)
        {
            HttpClient client = await InitClient();
            var url = $"{FirecRESTurl}/{resource}";

            // Get stream
            return await client.GetStreamAsync(url);
        }

        protected async Task<string> RequestPost(string resource, Dictionary<string, string> formData)
        {
            HttpClient client = await InitClient();
            string url = $"{FirecRESTurl}/{resource}";

            var jsonPayload = JsonSerializer.Serialize(formData);
            var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");
            HttpResponseMessage response = await client.PostAsync(url, content);
            response.EnsureSuccessStatusCode();

            // Decode response
            return await response.Content.ReadAsStringAsync();
        }

        protected async Task<string> RequestPost(string resource, MultipartFormDataContent formData)
        {
            HttpClient client = await InitClient();
            string url = $"{FirecRESTurl}/{resource}";

            HttpResponseMessage response = await client.PostAsync(url, formData);
            response.EnsureSuccessStatusCode();

            // Decode response
            return await response.Content.ReadAsStringAsync();
        }
    }
}
