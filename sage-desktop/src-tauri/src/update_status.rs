//! Shared update status enum.
//!
//! Lives outside the `commands` module so it compiles without the
//! `desktop` feature — lets the pure-Rust test suite exercise the
//! serialization contract that the frontend depends on.

use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
#[serde(tag = "kind")]
pub enum UpdateStatus {
    UpToDate {
        current_version: String,
    },
    Available {
        current_version: String,
        new_version: String,
        notes: String,
    },
    Error {
        detail: String,
    },
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn update_status_available_serializes_with_kind_tag() {
        let s = UpdateStatus::Available {
            current_version: "0.2.0".into(),
            new_version: "0.3.0".into(),
            notes: "fixes".into(),
        };
        let j = serde_json::to_string(&s).unwrap();
        assert!(j.contains(r#""kind":"Available""#), "{j}");
        assert!(j.contains(r#""new_version":"0.3.0""#), "{j}");
    }

    #[test]
    fn update_status_up_to_date_tag() {
        let s = UpdateStatus::UpToDate {
            current_version: "0.2.0".into(),
        };
        let j = serde_json::to_string(&s).unwrap();
        assert!(j.contains(r#""kind":"UpToDate""#), "{j}");
    }

    #[test]
    fn update_status_error_variant_carries_detail() {
        let s = UpdateStatus::Error {
            detail: "network timeout".into(),
        };
        let j = serde_json::to_string(&s).unwrap();
        assert!(j.contains(r#""kind":"Error""#), "{j}");
        assert!(j.contains("network timeout"), "{j}");
    }

    #[test]
    fn update_status_roundtrips_through_json() {
        let orig = UpdateStatus::Available {
            current_version: "1.0.0".into(),
            new_version: "1.1.0".into(),
            notes: "x".into(),
        };
        let j = serde_json::to_string(&orig).unwrap();
        let back: UpdateStatus = serde_json::from_str(&j).unwrap();
        assert_eq!(orig, back);
    }
}
