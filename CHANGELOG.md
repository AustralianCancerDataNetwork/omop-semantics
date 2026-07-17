# 0.1.0
- initial alpha release

# 0.1.1
- with runtime valuesets and defaults

# 0.1.2
- with tab completion for groups

# 0.1.3
- added missed mets concepts

# 0.1.4
- auto-collapse singleton parents for groups

# 0.1.5 
- fixing grade concepts

# 0.1.6
- added condition concepts
- added demographics concepts

# 0.1.7
- subclassed runtime group/enums
- semantic unknown handlers

# 0.1.8
- unknown concept handlers specified (thin at the moment)

# 0.1.9
- moved some enumerator definitions around

# 0.1.10
- visit modalities

# 0.1.11
- lab measurements

# 0.1.12
- ecog

# 0.1.13
- missed measurement_id

# 0.1.14
- dependabot alerts

# 0.1.15
- dependabot alerts

# 0.2.0
- significant cleanup to prepare for consumption in downstream groundworks mapping tasks

# 0.2.1
- clarified the public runtime surfaces and updated package documentation to reflect current end-user behavior

# 0.2.2
- naming clash for 'members' declared in >1 location
- light resolver cleanup
- fix KeyError type
- docs update

# 0.3.0
- added an executable output-definition layer so a grounded concept can deterministically project into one or more CDM rows, with richer profile shapes to describe them
- added deterministic handling for row values that depend on a separate source field, or that should suppress the row entirely, always recorded explicitly rather than silently dropped
- fully additive; existing grounding and profile behavior is unchanged
