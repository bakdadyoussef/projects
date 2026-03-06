import flet as ft
import random
import asyncio

def main(page: ft.Page):
    # ---------- THEME & STYLING ----------
    page.title = "Stellar Dashboard"
    page.theme_mode = ft.ThemeMode.DARK   # or LIGHT
    page.padding = 20
    page.spacing = 20
    page.bgcolor = "#1E1E2F"              # deep dark background

    # Custom color palette
    primary = "#6C5CE7"    # vibrant purple
    secondary = "#00B894"  # mint green
    accent = "#FF7675"      # soft red
    surface = "#2D2D44"     # card background
    text_primary = "#FFFFFF"
    text_secondary = "#B2BEC3"

    # ---------- NAVIGATION RAIL ----------
    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=200,
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.icons.DASHBOARD,   # solid icon (works in all versions)
                label="Dashboard",
            ),
            ft.NavigationRailDestination(
                icon=ft.icons.ANALYTICS,
                label="Analytics",
            ),
            ft.NavigationRailDestination(
                icon=ft.icons.SETTINGS,
                label="Settings",
            ),
        ],
        on_change=lambda e: print(f"Selected: {e.control.selected_index}"),
        bgcolor=surface,
        elevation=5,
    )

    # ---------- ANIMATED STAT CARD ----------
    def create_stat_card(title, value, icon, color, delta):
        return ft.Container(
            width=200,
            height=120,
            bgcolor=surface,
            border_radius=15,
            padding=15,
            animate=ft.animation.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
            on_hover=lambda e: setattr(e.control, "scale", 1.02 if e.data == "true" else 1.0) or e.control.update(),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, color=color, size=30),
                            ft.Text(title, size=14, color=text_secondary),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        [
                            ft.Text(value, size=28, weight=ft.FontWeight.BOLD, color=text_primary),
                            ft.Container(
                                content=ft.Text(delta, size=12, color="white"),
                                bgcolor=secondary if "+" in delta else accent,
                                border_radius=20,
                                padding=ft.padding.only(left=8, right=8, top=3, bottom=3),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=5,
            ),
        )

    # Stat cards data
    stats = [
        ("Revenue", "$54.2K", ft.icons.TRENDING_UP, secondary, "+12.3%"),
        ("Users", "8,549", ft.icons.PEOPLE, primary, "+5.7%"),
        ("Orders", "1,243", ft.icons.SHOPPING_CART, accent, "-2.1%"),
        ("Conversion", "3.8%", ft.icons.PERCENT, "#FDCB6E", "+0.8%"),
    ]

    cards_row = ft.Row(
        [create_stat_card(*stat) for stat in stats],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        scroll=ft.ScrollMode.AUTO,
    )

    # ---------- LINE CHART ----------
    chart_data = [
        ft.LineChartData(
            data_points=[
                ft.LineChartDataPoint(1, 12),
                ft.LineChartDataPoint(2, 25),
                ft.LineChartDataPoint(3, 18),
                ft.LineChartDataPoint(4, 30),
                ft.LineChartDataPoint(5, 22),
                ft.LineChartDataPoint(6, 35),
                ft.LineChartDataPoint(7, 40),
            ],
            stroke_width=3,
            color=primary,
            curved=True,
            stroke_cap_round=True,
        )
    ]

    chart = ft.LineChart(
        data_series=chart_data,
        border=ft.Border(bottom=ft.BorderSide(1, text_secondary)),
        left_axis=ft.ChartAxis(labels_size=40, title=ft.Text("Sales", size=12, color=text_secondary)),
        bottom_axis=ft.ChartAxis(labels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], labels_size=30),
        tooltip_bgcolor=surface,
        expand=True,
        min_y=0,
        max_y=50,
    )

    chart_container = ft.Container(
        content=chart,
        bgcolor=surface,
        border_radius=15,
        padding=20,
        height=250,
        animate=ft.animation.Animation(500, ft.AnimationCurve.EASE),
        shadow=ft.BoxShadow(blur_radius=10, color="#30000000", offset=ft.Offset(0, 5)),
    )

    # ---------- RECENT ACTIVITIES (LIST TILE) ----------
    activities = [
        ("Order #1234", "Completed", secondary, ft.icons.CHECK_CIRCLE),
        ("Order #1235", "Processing", accent, ft.icons.AUTORENEW),
        ("Order #1236", "Shipped", primary, ft.icons.LOCAL_SHIPPING),
    ]

    activity_list = ft.Column(
        [
            ft.ListTile(
                leading=ft.Icon(icon, color=color),
                title=ft.Text(title, color=text_primary),
                subtitle=ft.Text(status, color=text_secondary),
            )
            for title, status, color, icon in activities
        ],
        spacing=5,
    )

    activities_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("Recent Activities", size=18, weight=ft.FontWeight.BOLD, color=text_primary),
                ft.Divider(height=20, color=text_secondary),
                activity_list,
            ]
        ),
        bgcolor=surface,
        border_radius=15,
        padding=20,
        expand=True,
    )

    # ---------- MAIN CONTENT AREA (using ResponsiveRow for adaptability) ----------
    main_content = ft.ResponsiveRow(
        [
            ft.Column(col={"sm": 12, "md": 8}, controls=[cards_row, chart_container]),
            ft.Column(col={"sm": 12, "md": 4}, controls=[activities_card]),
        ],
        spacing=20,
        run_spacing=20,
    )

    # ---------- APP BAR ----------
    page.appbar = ft.AppBar(
        title=ft.Text("Stellar Dashboard", color=text_primary, weight=ft.FontWeight.BOLD),
        bgcolor=surface,
        elevation=0,
        actions=[
            ft.IconButton(icon=ft.icons.NOTIFICATIONS, icon_color=text_primary),  # solid icon
            ft.IconButton(icon=ft.icons.PERSON, icon_color=text_primary),        # solid icon
        ],
    )

    # ---------- PAGE LAYOUT (NavigationRail + main content) ----------
    page.add(
        ft.Row(
            [
                rail,
                ft.VerticalDivider(width=1, color=text_secondary),
                ft.Container(content=main_content, expand=True, padding=10),
            ],
            expand=True,
            spacing=0,
        )
    )

    # ---------- LIVE DATA UPDATE (simulate real‑time, async) ----------
    async def update_data():
        while True:
            # Randomly change chart data point (just for demo)
            new_point = random.randint(10, 45)
            chart.data_series[0].data_points[3].y = new_point
            chart.update()
            await asyncio.sleep(5)

    page.run_task(update_data)

ft.app(target=main)