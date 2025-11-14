/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Advanced Appointment Analytics Dashboard (TASK-F3-004)
 *
 * Interactive OWL component that displays comprehensive appointment analytics
 * with real-time data, charts, and filtering capabilities.
 */
class AppointmentDashboard extends Component {
    static template = "clinic_appointment_core.AppointmentDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            // Loading state
            loading: true,
            error: null,

            // Filters
            dateFrom: this._getDefaultDateFrom(),
            dateTo: this._getDefaultDateTo(),
            branchId: null,
            staffId: null,
            branches: [],
            staff: [],

            // Data
            kpis: {},
            appointmentsByStatus: [],
            appointmentsByType: [],
            appointmentsTimeline: [],
            topStaff: [],
            topServices: [],
            hourlyDistribution: [],
            branchPerformance: [],
            patientMetrics: {},
            revenueData: {},
        });

        onWillStart(async () => {
            await this.loadFiltersData();
            await this.loadDashboardData();
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    /**
     * Get default date from (30 days ago)
     */
    _getDefaultDateFrom() {
        const date = new Date();
        date.setDate(date.getDate() - 30);
        return date.toISOString().split('T')[0];
    }

    /**
     * Get default date to (today)
     */
    _getDefaultDateTo() {
        return new Date().toISOString().split('T')[0];
    }

    /**
     * Load filters data (branches, staff)
     */
    async loadFiltersData() {
        try {
            const filtersData = await this.orm.call(
                "clinic.appointment.dashboard",
                "get_filters_data",
                []
            );

            this.state.branches = filtersData.branches;
            this.state.staff = filtersData.staff;
        } catch (error) {
            console.error("Error loading filters:", error);
            this.state.error = "Failed to load filter options";
        }
    }

    /**
     * Load dashboard data with current filters
     */
    async loadDashboardData() {
        this.state.loading = true;
        this.state.error = null;

        try {
            const data = await this.orm.call(
                "clinic.appointment.dashboard",
                "get_dashboard_data",
                [],
                {
                    date_from: this.state.dateFrom,
                    date_to: this.state.dateTo,
                    branch_id: this.state.branchId,
                    staff_id: this.state.staffId,
                }
            );

            // Update state with fetched data
            this.state.kpis = data.kpis;
            this.state.appointmentsByStatus = data.appointments_by_status;
            this.state.appointmentsByType = data.appointments_by_type;
            this.state.appointmentsTimeline = data.appointments_timeline;
            this.state.topStaff = data.top_staff;
            this.state.topServices = data.top_services;
            this.state.hourlyDistribution = data.hourly_distribution;
            this.state.branchPerformance = data.branch_performance;
            this.state.patientMetrics = data.patient_metrics;
            this.state.revenueData = data.revenue_data;

            this.state.loading = false;

            // Re-render charts after data update
            setTimeout(() => this.renderCharts(), 100);
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.state.error = "Failed to load dashboard data";
            this.state.loading = false;
        }
    }

    /**
     * Render charts using Chart.js (if available)
     * Note: This assumes Chart.js is available. If not, charts won't render
     * but the dashboard will still show data in tables.
     */
    renderCharts() {
        if (typeof Chart === 'undefined') {
            console.warn("Chart.js not available. Charts will not render.");
            return;
        }

        this.renderStatusPieChart();
        this.renderTimelineChart();
        this.renderHourlyChart();
    }

    /**
     * Render status distribution pie chart
     */
    renderStatusPieChart() {
        const canvas = document.getElementById('statusChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');

        // Destroy existing chart if any
        if (this.statusChart) {
            this.statusChart.destroy();
        }

        const colors = {
            'draft': '#6c757d',
            'confirmed': '#007bff',
            'in_progress': '#ffc107',
            'completed': '#28a745',
            'cancelled': '#dc3545',
            'no_show': '#fd7e14'
        };

        this.statusChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: this.state.appointmentsByStatus.map(d => d.status),
                datasets: [{
                    data: this.state.appointmentsByStatus.map(d => d.count),
                    backgroundColor: this.state.appointmentsByStatus.map(d => colors[d.status] || '#6c757d')
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    /**
     * Render appointments timeline chart
     */
    renderTimelineChart() {
        const canvas = document.getElementById('timelineChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');

        // Destroy existing chart if any
        if (this.timelineChart) {
            this.timelineChart.destroy();
        }

        this.timelineChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: this.state.appointmentsTimeline.map(d => d.date),
                datasets: [{
                    label: 'Appointments',
                    data: this.state.appointmentsTimeline.map(d => d.count),
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }

    /**
     * Render hourly distribution bar chart
     */
    renderHourlyChart() {
        const canvas = document.getElementById('hourlyChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');

        // Destroy existing chart if any
        if (this.hourlyChart) {
            this.hourlyChart.destroy();
        }

        this.hourlyChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: this.state.hourlyDistribution.map(d => d.hour),
                datasets: [{
                    label: 'Appointments',
                    data: this.state.hourlyDistribution.map(d => d.count),
                    backgroundColor: '#28a745'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }

    /**
     * Handle filter change
     */
    async onFilterChange() {
        await this.loadDashboardData();
    }

    /**
     * Handle date from change
     */
    onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value;
        this.onFilterChange();
    }

    /**
     * Handle date to change
     */
    onDateToChange(ev) {
        this.state.dateTo = ev.target.value;
        this.onFilterChange();
    }

    /**
     * Handle branch filter change
     */
    onBranchChange(ev) {
        this.state.branchId = ev.target.value ? parseInt(ev.target.value) : null;
        this.onFilterChange();
    }

    /**
     * Handle staff filter change
     */
    onStaffChange(ev) {
        this.state.staffId = ev.target.value ? parseInt(ev.target.value) : null;
        this.onFilterChange();
    }

    /**
     * Refresh dashboard
     */
    async onRefresh() {
        await this.loadDashboardData();
    }

    /**
     * Get status badge class
     */
    getStatusBadgeClass(status) {
        const classes = {
            'draft': 'badge-secondary',
            'confirmed': 'badge-primary',
            'in_progress': 'badge-warning',
            'completed': 'badge-success',
            'cancelled': 'badge-danger',
            'no_show': 'badge-warning'
        };
        return classes[status] || 'badge-secondary';
    }

    /**
     * Format number with thousands separator
     */
    formatNumber(num) {
        return num.toLocaleString();
    }

    /**
     * Get growth icon
     */
    getGrowthIcon(percentage) {
        if (percentage > 0) return 'fa-arrow-up text-success';
        if (percentage < 0) return 'fa-arrow-down text-danger';
        return 'fa-minus text-muted';
    }
}

// Register the dashboard component
registry.category("actions").add("clinic_appointment_core.dashboard", AppointmentDashboard);

export default AppointmentDashboard;
