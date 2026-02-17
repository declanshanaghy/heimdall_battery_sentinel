import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

class HeimdallPanel extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      narrow: { type: Boolean },
      _allBatteries: { type: Array },
      _lowBatteries: { type: Array },
      _threshold: { type: Number },
      _loading: { type: Boolean },
      _showAllTable: { type: Boolean },
      _allTableLoading: { type: Boolean },
    };
  }

  constructor() {
    super();
    this._allBatteries = [];
    this._lowBatteries = [];
    this._threshold = 10;
    this._loading = true;
    this._showAllTable = false;
    this._allTableLoading = false;
    this._wsUnsubscribe = null;
  }

  connectedCallback() {
    super.connectedCallback();
    // Don't call _updateData here - hass isn't available yet
    // Wait for updated() to be called when hass is set
  }

  disconnectedCallback() {
    if (this._wsUnsubscribe) {
      this._wsUnsubscribe();
      this._wsUnsubscribe = null;
    }
    super.disconnectedCallback();
  }

  updated(changedProps) {
    console.log("Heimdall: entering 'updated' handler - %s", JSON.stringify(changedProps));

    if (changedProps.has("hass") && this.hass) {
      console.log("Heimdall: hass property updated, calling _updateData");
      this._updateData();
      this._subscribeToUpdates();
    }
  }

  async _subscribeToUpdates() {
    if (!this.hass?.subscribeWS || this._wsUnsubscribe) {
      return;
    }

    try {
      console.log("Heimdall: Subscribing to backend battery updates");
      this._wsUnsubscribe = await this.hass.subscribeWS(
        (event) => {
          console.log("Heimdall: Received battery update event", event);
          this._lowBatteries = event.low_batteries || [];
          if (this._showAllTable && event.all_batteries) {
            this._allBatteries = event.all_batteries || [];
          }
          this._threshold = event.threshold || 10;
          this._loading = false;
        },
        { type: "heimdall_battery_sentinel/subscribe_updates" }
      );
    } catch (err) {
      console.warn("Heimdall: Failed to subscribe to backend updates", err);
    }
  }

  async _updateData() {
    console.log("Heimdall: _updateData called");

    if (!this.hass) {
      console.warn("Heimdall: hass object not available yet");
      return;
    }

    console.log("Heimdall: hass object available, calling WebSocket API");
    this._loading = true;

    try {
      console.log("Heimdall: Calling heimdall_battery_sentinel/get_low_batteries via WebSocket");

      // Call the WebSocket API to get low battery data
      const result = await this.hass.callWS({
        type: "heimdall_battery_sentinel/get_low_batteries",
      });

      console.log("Heimdall: Low batteries WebSocket response received", result);
      this._lowBatteries = result.low_batteries || [];
      this._threshold = result.threshold || 10;
      console.log(`Heimdall: Loaded ${this._lowBatteries.length} low batteries`);
    } catch (err) {
      console.error("Heimdall: Error fetching data:", err);
      console.error("Heimdall: Error details:", {
        message: err.message,
        stack: err.stack,
      });
    } finally {
      this._loading = false;
      console.log("Heimdall: Loading complete");
    }
  }

  async _loadAllBatteries() {
    if (!this.hass) {
      return;
    }

    this._allTableLoading = true;
    try {
      console.log("Heimdall: Calling heimdall_battery_sentinel/get_all_batteries via WebSocket");
      const result = await this.hass.callWS({
        type: "heimdall_battery_sentinel/get_all_batteries",
      });
      console.log("Heimdall: All batteries WebSocket response received", result);
      this._allBatteries = result.all_batteries || [];
      this._threshold = result.threshold || this._threshold;
    } catch (err) {
      console.error("Heimdall: Error fetching all batteries:", err);
    } finally {
      this._allTableLoading = false;
    }
  }

  async _toggleAllTable() {
    const shouldShow = !this._showAllTable;
    this._showAllTable = shouldShow;
    if (shouldShow) {
      await this._loadAllBatteries();
    }
  }

  _getBatteryColor(battery) {
    if (battery.battery_level === null || isNaN(battery.battery_level)) {
      return "var(--disabled-text-color, #9e9e9e)";
    }
    if (battery.battery_level <= 5) return "var(--error-color, #f44336)";
    if (battery.is_low) return "var(--warning-color, #ff9800)";
    return "var(--success-color, #4caf50)";
  }

  _getRowClass(battery) {
    if (battery.is_low) return "row-low";
    return "row-ok";
  }

  _formatBatteryLevel(battery) {
    if (battery.battery_level === null || isNaN(battery.battery_level)) {
      return battery.state_value || "—";
    }
    return `${battery.battery_level.toFixed(1)}${battery.unit || "%"}`;
  }

  _renderBatteryTable(batteries, emptyMessage) {
    if (batteries.length === 0) {
      return html`
        <div class="empty-message">${emptyMessage}</div>
      `;
    }

    return html`
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Entity ID</th>
              <th>Friendly Name</th>
              <th>Battery Level</th>
            </tr>
          </thead>
          <tbody>
            ${batteries.map(
              (battery) => html`
                <tr class="${this._getRowClass(battery)}">
                  <td>
                    <code class="entity-id">${battery.entity_id}</code>
                  </td>
                  <td>
                    <span class="friendly-name">${battery.friendly_name}</span>
                  </td>
                  <td>
                    <span class="battery-value" style="color: ${this._getBatteryColor(battery)}">
                      ${this._formatBatteryLevel(battery)}
                    </span>
                  </td>
                </tr>
              `
            )}
          </tbody>
        </table>
      </div>
    `;
  }

  render() {
    if (this._loading) {
      return html`
        <div class="container">
          <div class="loading">
            <ha-icon icon="mdi:loading" class="loading-icon"></ha-icon>
            <p>Loading battery data...</p>
          </div>
        </div>
      `;
    }

    const lowCount = this._lowBatteries.length;

    return html`
      <div class="container">
        <div class="section">
          <h2>⚠️ Low Battery Devices</h2>
          <div class="all-count ${lowCount > 0 ? "count-warning" : ""}">
            ${this._lowBatteries.length} devices (≤${this._threshold}%)
          </div>
          ${this._renderBatteryTable(this._lowBatteries, "No low battery devices")}
        </div>

        <div class="section-separator" role="separator" aria-hidden="true"></div>

        <div class="section">
          <div class="all-section-header">
            <h2>📋 All Tracked Battery Entities</h2>
            <button class="toggle-button" @click=${this._toggleAllTable}>
              ${this._showAllTable ? "Hide Table" : "Show Table"}
            </button>
          </div>
          ${this._showAllTable
            ? html`
                <div class="all-count">${this._allBatteries.length} devices</div>
                ${this._allTableLoading
                  ? html`<div class="empty-message">Loading all tracked battery entities...</div>`
                  : this._renderBatteryTable(this._allBatteries, "No battery entities found")}
              `
            : ""}
        </div>
      </div>
    `;
  }

  static get styles() {
    return css`
      :host {
        display: block;
        padding: 16px;
        background-color: var(--primary-background-color);
        min-height: 100vh;
      }

      .container {
        max-width: 1400px;
        margin: 0 auto;
      }

      .section {
        margin-bottom: 32px;
      }

      .section-separator {
        height: 1px;
        margin: 8px 0 28px 0;
        background: linear-gradient(
          90deg,
          transparent 0%,
          var(--divider-color) 15%,
          var(--divider-color) 85%,
          transparent 100%
        );
      }

      .section h2 {
        margin: 0 0 16px 0;
        font-size: 20px;
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .empty-message {
        padding: 24px;
        text-align: center;
        color: var(--secondary-text-color);
        background-color: var(--card-background-color);
        border-radius: 8px;
        border: 2px dashed var(--divider-color);
      }

      .all-section-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 16px;
      }

      .all-section-header h2 {
        margin: 0;
      }

      .toggle-button {
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color);
        padding: 8px 12px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 14px;
      }

      .toggle-button:hover {
        background: var(--table-row-hover-color, rgba(0, 0, 0, 0.04));
      }

      .all-count {
        margin: 0 0 12px 0;
        color: var(--secondary-text-color);
        font-size: 14px;
      }

      .count-warning {
        color: var(--warning-color, #ff9800);
      }

      .loading {
        text-align: center;
        padding: 64px 16px;
      }

      .loading-icon {
        width: 48px;
        height: 48px;
        color: var(--primary-color);
        animation: spin 1s linear infinite;
      }

      @keyframes spin {
        from {
          transform: rotate(0deg);
        }
        to {
          transform: rotate(360deg);
        }
      }

      .loading p {
        margin: 16px 0 0 0;
        color: var(--secondary-text-color);
      }

      .empty-state {
        text-align: center;
        padding: 64px 16px;
      }

      .empty-icon {
        width: 64px;
        height: 64px;
        color: var(--secondary-text-color);
      }

      .empty-state h2 {
        margin: 16px 0 8px 0;
        font-size: 24px;
        font-weight: 400;
        color: var(--primary-text-color);
      }

      .empty-state p {
        margin: 0;
        color: var(--secondary-text-color);
      }

      .table-container {
        background-color: var(--card-background-color);
        border-radius: 8px;
        overflow-x: auto;
        box-shadow: var(
          --ha-card-box-shadow,
          0 2px 4px rgba(0, 0, 0, 0.1)
        );
      }

      table {
        width: 100%;
        border-collapse: collapse;
      }

      thead {
        background-color: var(--table-header-background-color, rgba(0, 0, 0, 0.05));
      }

      th {
        padding: 12px 16px;
        text-align: left;
        font-weight: 500;
        font-size: 12px;
        text-transform: uppercase;
        color: var(--secondary-text-color);
        border-bottom: 1px solid var(--divider-color);
        white-space: nowrap;
      }

      td {
        padding: 12px 16px;
        border-bottom: 1px solid var(--divider-color);
        font-size: 14px;
      }

      tbody tr:last-child td {
        border-bottom: none;
      }

      tbody tr:hover {
        background-color: var(--table-row-hover-color, rgba(0, 0, 0, 0.02));
      }

      .row-low {
        background-color: rgba(255, 152, 0, 0.08);
      }

      .entity-id {
        font-family: 'Roboto Mono', monospace;
        font-size: 12px;
        color: var(--secondary-text-color);
        background-color: rgba(0, 0, 0, 0.05);
        padding: 2px 6px;
        border-radius: 3px;
      }

      .friendly-name {
        color: var(--primary-text-color);
      }

      .battery-value {
        font-weight: 500;
        font-size: 15px;
      }
    `;
  }
}

customElements.define("heimdall-panel", HeimdallPanel);
