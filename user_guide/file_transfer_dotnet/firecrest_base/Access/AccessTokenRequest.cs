/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

using System.Text.Json;
using Microsoft.IdentityModel.JsonWebTokens;

namespace firecrest_base.Access
{
    public class AccessTokenRequest(string credentialsFile = ".credentials")
    {
        // Credentials data
        protected class Credentials
        {
            public string? ClientID { get; set; }
            public string? ClientSecret { get; set; }
            public string? Url { get; set; }

            public Credentials()
            {
            }
        }

        // Path to the credentials file
        private readonly string credentialsFile = credentialsFile;

        public async Task<AccessToken?> get()
        {
            try
            {
                // Read credentials from file
                var data = File.ReadAllText(credentialsFile);
                var credentials = JsonSerializer.Deserialize<Credentials>(data) ?? throw new Exception("Invalid credentials");

                // Check Credentials parameters
                if (credentials.Url is null)
                    throw new Exception("Credentials URL not set");
                if (credentials.ClientID is null)
                    throw new Exception("Credentials ClientID not set");
                if (credentials.ClientSecret is null)
                    throw new Exception("Credentials ClientSecret not set");

                // Prepare request's data
                Dictionary<string, string> formData = new Dictionary<string, string>
                {
                    { "grant_type",    "client_credentials" },
                    { "client_id",     credentials.ClientID },
                    { "client_secret", credentials.ClientSecret }
                };

                // Client for token request to AccessToken URL
                HttpClient client = new HttpClient();

                // Request new token
                client.DefaultRequestHeaders.Add("Accept", "*/*");
                HttpContent content = new FormUrlEncodedContent(formData);
                HttpResponseMessage response = await client.PostAsync(credentials.Url, content);
                response.EnsureSuccessStatusCode();

                // Decode response
                string body = await response.Content.ReadAsStringAsync();
                JsonElement json = JsonDocument.Parse(body).RootElement;

                // Get JWT access token
                string? access_token = json.GetProperty("access_token").GetString() ?? throw new Exception("Access token not found");

                // Decode JWT to extract expiration date and time
                JsonWebToken jwtSecurityToken = new JsonWebToken(access_token);
                DateTime exp = jwtSecurityToken.ValidTo;

                // Return new AccessToken
                return new AccessToken(access_token, exp);
            }
            catch (HttpRequestException e)
            {
                Console.WriteLine(e.Message);
                return null;
            }
        }
    }
}
