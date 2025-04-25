/*
 * Copyright (c) 2025, ETH Zurich. All rights reserved.
 *
 * Please, refer to the LICENSE file in the root directory.
 * SPDX-License-Identifier: BSD-3-Clause
 */

namespace firecrest_base.Access
{
    public class AccessToken(string token, DateTime exp)
    {
        public string Token { get; private set; } = token;
        public DateTime Exp { get; private set; } = exp;

        public bool HasExpired() {
            return DateTime.Now > Exp;
        }
    }
}
