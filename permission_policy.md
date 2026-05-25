# Agent Permission Policy

## Hardware Access (Granted)
The following groups grant hardware access for fast inference:
- `render`: GPU rendering access
- `video`: Video device access
- `audio`: Audio device access
- `storage`: Storage device access

Current user 'mark' membership:
- render: ✅
- video: ✅
- audio: ✅
- storage: ✅

## System Configuration (Locked)
The following system configurations should be locked to 'local version' to preserve stability:

### GRUB Configuration
- Location: `/etc/default/grub`
- Status: No GRUB configuration file exists (system uses Limine bootloader)
- Recommendation: If GRUB is used, lock to local version

### SSH Configuration
- Location: `/etc/ssh/sshd_config`
- Status: Standard OpenSSH configuration
- Recommendation: Lock to local version, prevent autonomous updates

### Update Policy
- System packages: Lock to local version
- Agent modules: Allow updates via guardian_manifest.json verification
- Core infrastructure: Lock to local version

## Implementation Notes
1. Grant hardware access explicitly via group membership
2. Lock system configs (grub/ssh) to 'local version'
3. Use guardian_manifest.json for agent module integrity verification
4. Implement pre-update hooks to verify system stability
