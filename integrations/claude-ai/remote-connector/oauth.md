# OAuth Configuration for Claude.ai Connector

The KiCad MCP remote server supports OAuth 2.1 / PKCE for secure authentication.

## Endpoints

```
Authorization endpoint:  https://auth.kicad.example.com/authorize
Token endpoint:          https://auth.kicad.example.com/token
JWKS endpoint:           https://auth.kicad.example.com/.well-known/jwks.json
```

## OAuth Protected Resource Metadata

```
.well-known/oauth-protected-resource
.well-known/oauth-authorization-server
```

## Scopes

| Scope | Access |
|-------|--------|
| `kicad:read` | Read-only tools and project data |
| `kicad:write` | Write/export tools (requires additional approval) |
| `kicad:bridge` | Local bridge pairing (requires pairing code) |

## Flow

1. Claude.ai initiates authorization via browser redirect
2. User authenticates and grants requested scopes
3. Authorization code is exchanged for access + refresh tokens
4. Token is stored securely in Claude.ai session

## Token Security

- Access tokens are short-lived (1 hour)
- Refresh tokens rotate on use
- Revoke tokens via the account settings page
- All API calls must use HTTPS
