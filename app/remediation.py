"""Developer-oriented remediation engine for Autonomous UI Auditor."""

PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

RULES = [
    ("occluded", "Remove or reposition the overlapping layer so the intended control remains visible, reachable and clickable at the tested viewport.", "Verify normal pointer interaction without force-click recovery."),
    ("unlabelled", "Add a meaningful accessible name using a visible label, aria-label, or aria-labelledby relationship.", "Re-run the accessibility audit and verify the accessible name."),
    ("form control may lack accessible name", "Associate every form control with a programmatic label and provide a meaningful accessible name.", "Check the control with keyboard and assistive-technology semantics."),
    ("target size", "Increase the interactive target to at least a comfortable touch/click size and preserve adequate spacing.", "Re-measure the rendered control at the tested viewport."),
    ("non-progressing", "Ensure the interaction produces clear state change or feedback and prevent repeated actions against the same state.", "Repeat the action and verify URL/content/state changes."),
    ("failed interaction", "Fix the interaction barrier identified in the evidence and expose a clear recovery path.", "Re-run the exact failing action and verify it completes normally."),
    ("unavailable", "Keep the no-results/unavailable state explicit. Do not silently substitute a different product.", "Test a matching request and a non-matching request separately."),
    ("out of stock", "Clearly expose stock status and prevent checkout of unavailable inventory while offering alternatives.", "Verify the requested item is blocked and the user receives a clear stock message."),
    ("no products", "Provide a clear no-results state with reset filters, alternative suggestions, or a way to refine the query.", "Search for an impossible combination and verify the recovery UI."),
    ("dead-end", "Add a clear recovery path such as Back, reset, alternative navigation, or contextual guidance.", "Repeat the path and verify the user can recover without restarting the entire journey."),
    ("regression", "Restore the V1 baseline behavior or intentionally document the changed behavior and its user impact.", "Re-run the same goal on V1 and V2 and compare checkpoints."),
]


def build_remediations(findings):
    result = []
    seen = set()
    for finding in findings:
        title = str(finding.get("title", "Finding"))
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        text = f"{title} {finding.get('evidence', '')}".lower()
        recommendation = "Review the cited UI state and remove the interaction, accessibility, or workflow barrier identified by the auditor."
        validation = "Re-run the affected workflow and verify the evidence is no longer present."
        for needle, rec, valid in RULES:
            if needle in text:
                recommendation, validation = rec, valid
                break
        priority = str(finding.get("severity", "MEDIUM")).upper()
        result.append({
            "finding": title,
            "priority": priority if priority in PRIORITY_ORDER else "MEDIUM",
            "recommendation": recommendation,
            "validation": validation,
        })
    return sorted(result, key=lambda x: PRIORITY_ORDER.get(x["priority"], 2))
