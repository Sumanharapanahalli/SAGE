//! Typed error enum shared by all Tauri commands.
//!
//! Maps JSON-RPC error codes from the Python sidecar (defined in
//! `sidecar/rpc.py`) onto strongly-typed Rust variants so the frontend
//! can render specific banners per error kind rather than a single
//! opaque "sidecar error" fallback.

use serde::{Deserialize, Serialize};
use thiserror::Error;

// JSON-RPC standard codes
pub const RPC_PARSE_ERROR: i32 = -32700;
pub const RPC_INVALID_REQUEST: i32 = -32600;
pub const RPC_METHOD_NOT_FOUND: i32 = -32601;
pub const RPC_INVALID_PARAMS: i32 = -32602;
pub const RPC_INTERNAL_ERROR: i32 = -32603;

// SAGE-specific codes (must match sidecar/rpc.py)
pub const RPC_SIDECAR_ERROR: i32 = -32000;
pub const RPC_PROPOSAL_EXPIRED: i32 = -32001;
pub const RPC_RBAC_DENIED: i32 = -32002;
pub const RPC_PROPOSAL_NOT_FOUND: i32 = -32003;
pub const RPC_SOLUTION_UNAVAILABLE: i32 = -32004;
pub const RPC_ALREADY_DECIDED: i32 = -32005;
pub const RPC_SAGE_IMPORT_ERROR: i32 = -32010;
pub const RPC_FEATURE_REQUEST_NOT_FOUND: i32 = -32020;
pub const RPC_SOLUTION_NOT_FOUND: i32 = -32021;

#[derive(Debug, Error, Serialize, Deserialize, Clone, PartialEq)]
#[serde(tag = "kind", content = "detail")]
pub enum DesktopError {
    #[error("proposal not found: {trace_id}")]
    ProposalNotFound { trace_id: String },

    #[error("proposal expired: {trace_id}")]
    ProposalExpired { trace_id: String },

    #[error("proposal already {status}: {trace_id}")]
    AlreadyDecided { trace_id: String, status: String },

    #[error("RBAC denied — required role: {required_role}")]
    RbacDenied { required_role: String },

    #[error("solution unavailable: {message}")]
    SolutionUnavailable { message: String },

    #[error("cannot import SAGE module '{module}': {detail}")]
    SageImportError { module: String, detail: String },

    #[error("invalid request: {message}")]
    InvalidRequest { message: String },

    #[error("invalid params: {message}")]
    InvalidParams { message: String },

    #[error("method not found: {method}")]
    MethodNotFound { method: String },

    #[error("sidecar crashed or unreachable: {message}")]
    SidecarDown { message: String },

    #[error("feature request not found: {feature_id}")]
    FeatureRequestNotFound { feature_id: String },

    #[error("solution not found: {name}")]
    SolutionNotFound { name: String },

    #[error("sidecar error ({code}): {message}")]
    Other { code: i32, message: String },
}

impl DesktopError {
    /// Build a typed DesktopError from the raw JSON-RPC error payload.
    ///
    /// `data` is a `serde_json::Value` carrying structured context such
    /// as `trace_id`, `status`, `module`, etc. Missing fields fall back
    /// to safe defaults rather than panicking.
    pub fn from_rpc(code: i32, message: String, data: Option<serde_json::Value>) -> Self {
        let get_str = |key: &str| -> String {
            data.as_ref()
                .and_then(|d| d.get(key))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
        };

        match code {
            RPC_PROPOSAL_NOT_FOUND => DesktopError::ProposalNotFound {
                trace_id: get_str("trace_id"),
            },
            RPC_PROPOSAL_EXPIRED => DesktopError::ProposalExpired {
                trace_id: get_str("trace_id"),
            },
            RPC_ALREADY_DECIDED => DesktopError::AlreadyDecided {
                trace_id: get_str("trace_id"),
                status: get_str("status"),
            },
            RPC_RBAC_DENIED => DesktopError::RbacDenied {
                required_role: get_str("required_role"),
            },
            RPC_SOLUTION_UNAVAILABLE => DesktopError::SolutionUnavailable { message },
            RPC_SAGE_IMPORT_ERROR => DesktopError::SageImportError {
                module: get_str("module"),
                detail: get_str("detail"),
            },
            RPC_INVALID_REQUEST => DesktopError::InvalidRequest { message },
            RPC_INVALID_PARAMS => DesktopError::InvalidParams { message },
            RPC_METHOD_NOT_FOUND => {
                // The sidecar embeds the method name in the message:
                // "method not found: X"
                let method = message
                    .strip_prefix("method not found: ")
                    .unwrap_or(&message)
                    .to_string();
                DesktopError::MethodNotFound { method }
            }
            RPC_FEATURE_REQUEST_NOT_FOUND => DesktopError::FeatureRequestNotFound {
                feature_id: get_str("feature_id"),
            },
            RPC_SOLUTION_NOT_FOUND => DesktopError::SolutionNotFound {
                name: get_str("name"),
            },
            _ => DesktopError::Other { code, message },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn proposal_not_found_extracts_trace_id() {
        let err = DesktopError::from_rpc(
            RPC_PROPOSAL_NOT_FOUND,
            "proposal not found".into(),
            Some(json!({"trace_id": "abc-123"})),
        );
        assert_eq!(
            err,
            DesktopError::ProposalNotFound {
                trace_id: "abc-123".into()
            }
        );
    }

    #[test]
    fn already_decided_extracts_trace_id_and_status() {
        let err = DesktopError::from_rpc(
            RPC_ALREADY_DECIDED,
            "already approved".into(),
            Some(json!({"trace_id": "xyz", "status": "approved"})),
        );
        assert_eq!(
            err,
            DesktopError::AlreadyDecided {
                trace_id: "xyz".into(),
                status: "approved".into()
            }
        );
    }

    #[test]
    fn method_not_found_extracts_method_from_message() {
        let err = DesktopError::from_rpc(
            RPC_METHOD_NOT_FOUND,
            "method not found: foo.bar".into(),
            None,
        );
        assert_eq!(
            err,
            DesktopError::MethodNotFound {
                method: "foo.bar".into()
            }
        );
    }

    #[test]
    fn unknown_code_falls_back_to_other() {
        let err = DesktopError::from_rpc(-99999, "weird thing".into(), None);
        assert_eq!(
            err,
            DesktopError::Other {
                code: -99999,
                message: "weird thing".into()
            }
        );
    }

    #[test]
    fn sage_import_error_extracts_module_and_detail() {
        let err = DesktopError::from_rpc(
            RPC_SAGE_IMPORT_ERROR,
            "cannot import".into(),
            Some(json!({"module": "src.core.xxx", "detail": "No module named 'xxx'"})),
        );
        assert_eq!(
            err,
            DesktopError::SageImportError {
                module: "src.core.xxx".into(),
                detail: "No module named 'xxx'".into(),
            }
        );
    }

    #[test]
    fn missing_data_fields_use_empty_string_defaults() {
        let err = DesktopError::from_rpc(RPC_PROPOSAL_NOT_FOUND, "x".into(), None);
        assert_eq!(
            err,
            DesktopError::ProposalNotFound {
                trace_id: "".into()
            }
        );
    }

    #[test]
    fn display_format_includes_context() {
        let err = DesktopError::AlreadyDecided {
            trace_id: "t1".into(),
            status: "rejected".into(),
        };
        assert_eq!(err.to_string(), "proposal already rejected: t1");
    }

    #[test]
    fn solution_not_found_extracts_name() {
        let err = DesktopError::from_rpc(
            RPC_SOLUTION_NOT_FOUND,
            "solution not found".into(),
            Some(json!({ "name": "yoga" })),
        );
        assert_eq!(
            err,
            DesktopError::SolutionNotFound {
                name: "yoga".into()
            }
        );
    }

    #[test]
    fn feature_request_not_found_extracts_feature_id() {
        let err = DesktopError::from_rpc(
            RPC_FEATURE_REQUEST_NOT_FOUND,
            "feature request not found: abc".into(),
            Some(json!({"feature_id": "abc"})),
        );
        assert_eq!(
            err,
            DesktopError::FeatureRequestNotFound {
                feature_id: "abc".into()
            }
        );
    }

    #[test]
    fn serializes_as_tagged_json() {
        let err = DesktopError::ProposalNotFound {
            trace_id: "t1".into(),
        };
        let json = serde_json::to_value(&err).unwrap();
        assert_eq!(json["kind"], "ProposalNotFound");
        assert_eq!(json["detail"]["trace_id"], "t1");
    }
}
