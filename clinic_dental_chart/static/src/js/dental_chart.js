/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * TASK-F2-010: Interactive Dental Chart OWL Component
 *
 * Features:
 * - Visual representation of all 32 adult teeth
 * - Click teeth to view/add procedures
 * - Color-coded tooth states (healthy, cavity, filled, missing, etc.)
 * - Support for multiple notation systems (Universal, Palmer, FDI)
 * - Real-time updates from backend
 */
export class DentalChart extends Component {
    static template = "clinic_dental_chart.DentalChart";
    static props = {
        patientId: { type: Number, optional: false },
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");

        this.state = useState({
            teeth: [],
            selectedTooth: null,
            notationSystem: 'universal', // universal, palmer, fdi
            loading: true,
            quadrant: 'all', // all, upper, lower, upper_right, upper_left, lower_right, lower_left
        });

        // Tooth number mappings for different notation systems
        this.toothNumbers = {
            universal: Array.from({length: 32}, (_, i) => i + 1),
            palmer: this._generatePalmerNotation(),
            fdi: this._generateFDINotation(),
        };

        onWillStart(async () => {
            await this.loadTeethData();
        });
    }

    /**
     * Load teeth data from backend
     */
    async loadTeethData() {
        try {
            const teeth = await this.orm.searchRead(
                "clinic.tooth",
                [["patient_id", "=", this.props.patientId]],
                ["tooth_number", "notation_system", "status", "last_procedure_date", "notes"],
                { order: "tooth_number" }
            );

            // Initialize missing teeth if needed
            if (teeth.length === 0) {
                await this._initializeTeeth();
                await this.loadTeethData();
                return;
            }

            this.state.teeth = teeth;
            this.state.loading = false;
        } catch (error) {
            console.error("Error loading teeth data:", error);
            this.state.loading = false;
        }
    }

    /**
     * Initialize 32 teeth records for patient
     */
    async _initializeTeeth() {
        const teethData = [];
        for (let i = 1; i <= 32; i++) {
            teethData.push({
                patient_id: this.props.patientId,
                tooth_number: i,
                notation_system: 'universal',
                status: 'healthy',
            });
        }
        await this.orm.create("clinic.tooth", teethData);
    }

    /**
     * Generate Palmer notation (1-8 per quadrant)
     */
    _generatePalmerNotation() {
        const notation = [];
        const quadrants = ['UR', 'UL', 'LL', 'LR'];
        for (const quad of quadrants) {
            for (let i = 1; i <= 8; i++) {
                notation.push(`${quad}${i}`);
            }
        }
        return notation;
    }

    /**
     * Generate FDI notation (11-18, 21-28, 31-38, 41-48)
     */
    _generateFDINotation() {
        const notation = [];
        for (const quadrant of [1, 2, 3, 4]) {
            for (let tooth = 1; tooth <= 8; tooth++) {
                notation.push(parseInt(`${quadrant}${tooth}`));
            }
        }
        return notation;
    }

    /**
     * Handle tooth click - open procedure dialog
     */
    async onToothClick(tooth) {
        if (this.props.readonly) return;

        this.state.selectedTooth = tooth.id;

        // Open procedure action for this tooth
        this.action.doAction({
            type: "ir.actions.act_window",
            name: `Tooth ${tooth.tooth_number} - Procedures`,
            res_model: "clinic.dental.procedure",
            views: [[false, "list"], [false, "form"]],
            domain: [["tooth_id", "=", tooth.id]],
            context: {
                default_tooth_id: tooth.id,
                default_patient_id: this.props.patientId,
            },
            target: "new",
        });
    }

    /**
     * Get CSS class for tooth based on status
     */
    getToothClass(tooth) {
        const baseClass = "o_dental_tooth";
        const statusClass = `o_dental_tooth_${tooth.status}`;
        const selectedClass = tooth.id === this.state.selectedTooth ? "o_dental_tooth_selected" : "";
        return `${baseClass} ${statusClass} ${selectedClass}`;
    }

    /**
     * Get tooltip text for tooth
     */
    getToothTooltip(tooth) {
        let tooltip = `Tooth ${tooth.tooth_number}\nStatus: ${tooth.status}`;
        if (tooth.last_procedure_date) {
            tooltip += `\nLast Procedure: ${tooth.last_procedure_date}`;
        }
        if (tooth.notes) {
            tooltip += `\nNotes: ${tooth.notes}`;
        }
        return tooltip;
    }

    /**
     * Filter teeth by quadrant
     */
    getFilteredTeeth() {
        if (this.state.quadrant === 'all') {
            return this.state.teeth;
        }

        const quadrantRanges = {
            upper: [1, 16],
            lower: [17, 32],
            upper_right: [1, 8],
            upper_left: [9, 16],
            lower_left: [17, 24],
            lower_right: [25, 32],
        };

        const [start, end] = quadrantRanges[this.state.quadrant];
        return this.state.teeth.filter(t => t.tooth_number >= start && t.tooth_number <= end);
    }

    /**
     * Change notation system
     */
    changeNotation(system) {
        this.state.notationSystem = system;
    }

    /**
     * Change quadrant filter
     */
    changeQuadrant(quadrant) {
        this.state.quadrant = quadrant;
    }

    /**
     * Refresh chart data
     */
    async refreshChart() {
        this.state.loading = true;
        await this.loadTeethData();
    }
}

// Register as a field widget so it can be used in form views
registry.category("fields").add("dental_chart", {
    component: DentalChart,
});
