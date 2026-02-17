# Development Guide

## Implementation Summary

The Heimdall Battery Sentinel integration has been fully implemented according to the PRD and ERD specifications. All core components are in place and ready for testing.

## What Was Implemented

### Core Files

1. **manifest.json** - Integration metadata and dependencies
2. **const.py** - Constants and configuration keys
3. **config_flow.py** - UI configuration flow and options flow
4. **__init__.py** - Main integration logic with:
   - Battery entity discovery
   - Event-driven state monitoring
   - Panel registration
   - Low battery tracking
5. **strings.json & translations/en.json** - UI strings for config flow
6. **frontend/panel.js** - LitElement web component for the panel UI
7. **frontend/panel.html** - HTML wrapper for the panel

### Key Features Implemented

✅ Automatic battery entity discovery (device_class, entity_id, attributes)
✅ Event-driven monitoring (no polling)
✅ Config flow with threshold setting
✅ Options flow for updating threshold
✅ Custom sidebar panel with table view
✅ Battery level color coding (red ≤ 5%, orange ≤ threshold)
✅ Area/room display for each device
✅ Historical trend sparklines (30-day)
✅ Empty state when all batteries are healthy
✅ Automatic removal when battery recovers
✅ Sorting by battery level (lowest first)

## Testing Checklist

### Installation Testing

- [ ] Copy `custom_components/heimdall_battery_sentinel` to Home Assistant
- [ ] Restart Home Assistant
- [ ] Check for any errors in the logs
- [ ] Verify integration appears in the integrations list

### Configuration Testing

- [ ] Add integration via UI (Settings → Devices & Services)
- [ ] Verify default threshold is 20%
- [ ] Change threshold via options flow
- [ ] Verify threshold change takes effect immediately
- [ ] Test YAML configuration (optional)

### Discovery Testing

- [ ] Verify battery entities are discovered
- [ ] Check entities with `device_class: battery`
- [ ] Check entities with "battery" in entity_id
- [ ] Check entities with battery attributes
- [ ] Add a new battery device and verify it's discovered

### Monitoring Testing

- [ ] Create a test battery entity with level below threshold
- [ ] Verify it appears in the panel
- [ ] Change battery level above threshold
- [ ] Verify it's removed from the panel
- [ ] Test with unavailable/unknown states
- [ ] Monitor logs for any errors

### Panel Testing

- [ ] Verify "Batteries" appears in sidebar
- [ ] Click panel and verify it loads
- [ ] Check table displays correctly with all columns
- [ ] Verify battery icons match levels
- [ ] Verify colors are correct (red/orange)
- [ ] Check area names display correctly
- [ ] Verify sparklines render for entities with history
- [ ] Test empty state when no low batteries
- [ ] Verify sorting (lowest battery first)

### Edge Cases

- [ ] Test with 0 battery entities
- [ ] Test with 100+ battery entities
- [ ] Test with entities that have no area assigned
- [ ] Test with entities that have no history
- [ ] Test threshold edge cases (exactly at threshold)
- [ ] Test with non-numeric battery states

## Known Limitations

1. **Panel Type**: Uses iframe panel which may have some styling limitations
2. **History Data**: Requires Home Assistant's recorder to be enabled
3. **Real-time Updates**: Frontend panel refreshes on hass object changes (may not be instant)
4. **YAML Config**: YAML configuration is supported but config entries take precedence

## Potential Improvements (Future)

These are explicitly out of scope for v1.0 but could be added later:

- Per-device threshold overrides
- Push notifications or persistent notifications
- Device include/exclude lists
- Area-based filtering
- Export/import of low battery list
- Custom sorting options
- Battery replacement tracking/history
- Estimated time until battery depleted
- HACS distribution
- Multiple language translations

## Debugging Tips

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.heimdall_battery_sentinel: debug
```

### Check Integration Status

```python
# In Developer Tools → Template
{{ states.sensor | selectattr('attributes.device_class', 'eq', 'battery') | list | count }}
```

### Inspect Low Battery Data

The integration stores low battery data in `hass.data[DOMAIN][entry_id][DATA_LOW_BATTERIES]`. This can be inspected via logs or by adding a debug service.

### Panel Not Loading

1. Check browser console for JavaScript errors
2. Verify static paths are registered (check logs)
3. Clear browser cache
4. Check that LitElement CDN is accessible

## File Paths

When installed, the integration should be at:

```
<config_directory>/custom_components/heimdall_battery_sentinel/
```

Panel files are served from:
- `/api/heimdall_battery_sentinel/panel.html`
- `/api/heimdall_battery_sentinel/panel.js`

## Next Steps

1. **Install**: Copy the integration to your Home Assistant instance
2. **Test**: Run through the testing checklist above
3. **Iterate**: Fix any bugs or issues that arise
4. **Document**: Update README with any additional notes from testing
5. **Deploy**: Use the integration in production

## Contributing

Since this is a homebrew project, feel free to:
- Add additional battery discovery methods
- Enhance the frontend panel UI
- Add more configuration options
- Improve error handling
- Add unit tests (when ready for that phase)

## Support

For issues during development:
1. Check Home Assistant logs for errors
2. Enable debug logging for detailed information
3. Verify all files are in the correct locations
4. Ensure Home Assistant version compatibility
