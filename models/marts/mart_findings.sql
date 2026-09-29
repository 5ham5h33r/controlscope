with hits as (
    select * from {{ ref('int_control_hits') }}
    union all
    select * from {{ ref('int_anomaly_hits') }}
),
scored as (
    select to_hex(sha256(concat(h.control_id, '|', h.entity_id, '|', h.evidence_refs))) as finding_id,
           h.control_id, r.control_version, r.kind, h.entity_id, h.business_unit,
           h.evidence_refs, cast(r.base_risk as int64) as base_risk,
           least(100, cast(r.base_risk as int64) +
             least(15, 5 * (array_length(json_value_array(h.evidence_refs)) - 1))) as risk_score
    from hits h join {{ ref('control_registry') }} r using (control_id)
)
select * from scored
