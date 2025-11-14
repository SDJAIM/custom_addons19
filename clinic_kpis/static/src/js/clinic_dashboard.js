/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

/**
 * TASK-F3-004: Advanced Analytics Dashboard (OWL)
 *
 * Interactive dashboard with real-time KPIs:
 * - Today's appointments
 * - Revenue MTD
 * - New patients
 * - No-show rate
 * - Staff utilization
 * - Revenue trend chart
 */
class ClinicDashboard extends Component {
    static template = "clinic_kpis.ClinicDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.chartRefs = {
            revenueChart: useRef("revenueChart"),
            utilizationChart: useRef("utilizationChart"),
            proceduresChart: useRef("proceduresChart"),
        };

        this.state = useState({
            period: 'month',  // week, month, year
            dashboardId: null,
            dashboardName: 'Dashboard',
            lastRefresh: null,
            loading: true,
            kpis: {},
            revenueChartData: null,
        });

        this.charts = {};

        onWillStart(async () => {
            // Load Chart.js library
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.loadDashboardData();
        });

        onMounted(() => {
            this.renderCharts();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;

        try {
            // Get dashboard KPI data
            const data = await this.orm.call(
                "clinic.kpi.dashboard",
                "get_dashboard_data",
                [],
                {}
            );

            this.state.dashboardId = data.dashboard_id;
            this.state.dashboardName = data.dashboard_name;
            this.state.lastRefresh = data.last_refresh;
            this.state.kpis = data.kpis;

            // Get revenue chart data
            const revenueData = await this.orm.call(
                "clinic.kpi.dashboard",
                "get_revenue_chart_data",
                [],
                { period: this.state.period }
            );

            this.state.revenueChartData = revenueData;
            this.state.loading = false;

            // Re-render charts after data is loaded
            setTimeout(() => this.renderCharts(), 100);

        } catch (error) {
            console.error("Failed to load dashboard data:", error);
            this.state.loading = false;
        }
    }

    renderCharts() {
        // Destroy existing charts
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.charts = {};

        // Revenue Trend Chart (Line Chart)
        if (this.chartRefs.revenueChart.el && this.state.revenueChartData) {
            const ctx = this.chartRefs.revenueChart.el.getContext('2d');
            this.charts.revenue = new Chart(ctx, {
                type: 'line',
                data: this.state.revenueChartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: 'Revenue Trend'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return '$' + value.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });
        }

        // Staff Utilization Chart (Bar Chart)
        if (this.chartRefs.utilizationChart.el && this.state.kpis.staff_utilization) {
            const utilData = this.state.kpis.staff_utilization.staff || [];
            const ctx = this.chartRefs.utilizationChart.el.getContext('2d');
            this.charts.utilization = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: utilData.map(s => s.name),
                    datasets: [{
                        label: 'Utilization %',
                        data: utilData.map(s => s.utilization),
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: 'Staff Utilization Today'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        }
                    }
                }
            });
        }

        // Top Procedures Chart (Doughnut Chart)
        if (this.chartRefs.proceduresChart.el && this.state.kpis.top_procedures) {
            const procedures = this.state.kpis.top_procedures.procedures || [];
            const ctx = this.chartRefs.proceduresChart.el.getContext('2d');
            this.charts.procedures = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: procedures.map(p => p.name),
                    datasets: [{
                        data: procedures.map(p => p.count),
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.5)',
                            'rgba(54, 162, 235, 0.5)',
                            'rgba(255, 206, 86, 0.5)',
                            'rgba(75, 192, 192, 0.5)',
                            'rgba(153, 102, 255, 0.5)',
                        ],
                        borderColor: [
                            'rgba(255, 99, 132, 1)',
                            'rgba(54, 162, 235, 1)',
                            'rgba(255, 206, 86, 1)',
                            'rgba(75, 192, 192, 1)',
                            'rgba(153, 102, 255, 1)',
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right'
                        },
                        title: {
                            display: true,
                            text: 'Top Procedures This Month'
                        }
                    }
                }
            });
        }
    }

    async onPeriodChange(period) {
        this.state.period = period;
        await this.loadDashboardData();
    }

    async onRefresh() {
        await this.loadDashboardData();
    }

    onKpiClick(kpiName) {
        // Navigate to detailed view based on KPI
        if (kpiName === 'appointments_today') {
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'clinic.appointment',
                domain: [
                    ['start', '>=', new Date().toISOString().split('T')[0] + ' 00:00:00'],
                    ['start', '<=', new Date().toISOString().split('T')[0] + ' 23:59:59']
                ],
                views: [[false, 'kanban'], [false, 'list'], [false, 'form']],
                target: 'current',
                context: {},
            });
        } else if (kpiName === 'new_patients') {
            const today = new Date();
            const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'clinic.patient',
                domain: [
                    ['create_date', '>=', firstDay.toISOString()]
                ],
                views: [[false, 'list'], [false, 'form']],
                target: 'current',
                context: {},
            });
        }
    }

    getTrendIcon(trend) {
        if (!trend) return '';
        return trend.direction === 'up' ? '↑' : trend.direction === 'down' ? '↓' : '→';
    }

    getTrendClass(trend) {
        if (!trend) return '';
        return trend.direction === 'up' ? 'text-success' : trend.direction === 'down' ? 'text-danger' : 'text-muted';
    }

    getStateLabel(state) {
        const labels = {
            'draft': 'Draft',
            'confirmed': 'Confirmed',
            'arrived': 'Arrived',
            'in_progress': 'In Progress',
            'done': 'Done',
            'no_show': 'No Show',
            'cancelled': 'Cancelled',
        };
        return labels[state] || state;
    }
}

registry.category("actions").add("clinic_kpis.dashboard", ClinicDashboard);

export default ClinicDashboard;
