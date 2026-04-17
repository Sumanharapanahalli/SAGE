//! JSON-RPC 2.0 request/response types for NDJSON framing.
//!
//! Kept pure (no I/O) so it can be unit-tested without spawning a sidecar.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;

use crate::errors::DesktopError;

#[derive(Debug, Serialize)]
pub struct RpcRequest<'a> {
    pub jsonrpc: &'static str,
    pub id: String,
    pub method: &'a str,
    pub params: Value,
}

impl<'a> RpcRequest<'a> {
    pub fn new(method: &'a str, params: Value) -> Self {
        Self {
            jsonrpc: "2.0",
            id: Uuid::new_v4().to_string(),
            method,
            params,
        }
    }

    /// Serialize as a single NDJSON line (ending with \n).
    pub fn to_ndjson_line(&self) -> serde_json::Result<String> {
        let mut s = serde_json::to_string(self)?;
        s.push('\n');
        Ok(s)
    }
}

#[derive(Debug, Deserialize, Clone)]
pub struct RpcResponse {
    pub jsonrpc: String,
    pub id: Option<String>,
    #[serde(default)]
    pub result: Option<Value>,
    #[serde(default)]
    pub error: Option<RpcErrorObject>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct RpcErrorObject {
    pub code: i32,
    pub message: String,
    #[serde(default)]
    pub data: Option<Value>,
}

impl RpcResponse {
    /// Convert the response into a `Result<Value, DesktopError>` —
    /// success → inner result; error frame → typed DesktopError.
    pub fn into_result(self) -> Result<Value, DesktopError> {
        if let Some(err) = self.error {
            return Err(DesktopError::from_rpc(err.code, err.message, err.data));
        }
        Ok(self.result.unwrap_or(Value::Null))
    }
}

/// Parse one NDJSON line into a typed response.
pub fn parse_response_line(line: &str) -> Result<RpcResponse, DesktopError> {
    serde_json::from_str(line.trim()).map_err(|e| DesktopError::SidecarDown {
        message: format!("malformed response: {e}"),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn request_serializes_as_jsonrpc_2() {
        let req = RpcRequest::new("handshake", json!({}));
        let line = req.to_ndjson_line().unwrap();
        assert!(line.ends_with('\n'));
        let v: Value = serde_json::from_str(line.trim()).unwrap();
        assert_eq!(v["jsonrpc"], "2.0");
        assert_eq!(v["method"], "handshake");
        assert!(v["id"].is_string());
    }

    #[test]
    fn request_generates_unique_ids() {
        let a = RpcRequest::new("x", json!({}));
        let b = RpcRequest::new("x", json!({}));
        assert_ne!(a.id, b.id);
    }

    #[test]
    fn parse_response_success() {
        let line =
            r#"{"jsonrpc":"2.0","id":"1","result":{"health":"ok"}}"#;
        let resp = parse_response_line(line).unwrap();
        assert_eq!(resp.id.as_deref(), Some("1"));
        let val = resp.into_result().unwrap();
        assert_eq!(val["health"], "ok");
    }

    #[test]
    fn parse_response_error_maps_to_desktop_error() {
        let line = r#"{"jsonrpc":"2.0","id":"1","error":{"code":-32003,"message":"not found","data":{"trace_id":"abc"}}}"#;
        let resp = parse_response_line(line).unwrap();
        let err = resp.into_result().unwrap_err();
        assert_eq!(
            err,
            DesktopError::ProposalNotFound {
                trace_id: "abc".into()
            }
        );
    }

    #[test]
    fn parse_response_malformed_returns_sidecar_down() {
        let err = parse_response_line("not json").unwrap_err();
        assert!(matches!(err, DesktopError::SidecarDown { .. }));
    }

    #[test]
    fn parse_response_ignores_trailing_whitespace() {
        let line = "{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"result\":null}\n\n";
        assert!(parse_response_line(line).is_ok());
    }

    #[test]
    fn response_with_null_id_is_valid() {
        let line = r#"{"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"parse"}}"#;
        let resp = parse_response_line(line).unwrap();
        assert!(resp.id.is_none());
        assert!(resp.into_result().is_err());
    }
}
