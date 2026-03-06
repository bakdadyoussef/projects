import flet as ft
import random
import time

def main(page: ft.Page):
    # Page setup
    page.title = "Stunning Dashboard"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 30
    page.bgcolor = ft.colors.with_opacity(0.9, "#0B0F1E")  # dark background
    page.scroll = ft.ScrollMode.AUTO

    # Custom theme
    page.theme = ft.Theme(
        color_scheme_seed="blue",
        font_family="Poppins",
    )
    page.fonts = {
        "Poppins": "https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap"
    }

    # Helper to create gradient containers
    def gradient_container(content, colors, border_radius=20):
        return ft.Container(
            content=content,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=colors,
            ),
            border_radius=border_radius,
            padding=20,
            animate=ft.animation.Animation(300, "easeInOut"),
        )

    # Header with avatar
    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Welcome back, Alex", size=32, weight=ft.FontWeight.BOLD),
            ft.CircleAvatar(
                content=ft.Image(src="https://picsum.photos/200/200", fit=ft.ImageFit.COVER),
                radius=30,
            ),
        ],
    )

    # Stats cards (with animated counters)
    stats = ft.Row(
        spacing=20,
        controls=[
            gradient_container(
                ft.Column([
                    ft.Icon(ft.icons.SHOW_CHART, color=ft.colors.WHITE, size=40),
                    ft.Text("Total Sales", size=16, opacity=0.8),
                    ft.Text("$12,345", size=32, weight=ft.FontWeight.BOLD),
                    ft.Text("+15% from last month", size=12, opacity=0.7),
                ]),
                colors=[ft.colors.BLUE_400, ft.colors.PURPLE_400],
            ),
            gradient_container(
                ft.Column([
                    ft.Icon(ft.icons.PEOPLE, color=ft.colors.WHITE, size=40),
                    ft.Text("New Users", size=16, opacity=0.8),
                    ft.Text("1,234", size=32, weight=ft.FontWeight.BOLD),
                    ft.Text("+5.6% from last week", size=12, opacity=0.7),
                ]),
                colors=[ft.colors.GREEN_400, ft.colors.TEAL_400],
            ),
            gradient_container(
                ft.Column([
                    ft.Icon(ft.icons.ASSIGNMENT, color=ft.colors.WHITE, size=40),
                    ft.Text("Active Projects", size=16, opacity=0.8),
                    ft.Text("23", size=32, weight=ft.FontWeight.BOLD),
                    ft.Text("3 in review", size=12, opacity=0.7),
                ]),
                colors=[ft.colors.ORANGE_400, ft.colors.RED_400],
            ),
        ],
    )

    # Recent activities list with animated tiles
    activities = ft.ListView(
        spacing=10,
        padding=10,
        height=200,
        controls=[
            ft.ListTile(
                leading=ft.Icon(ft.icons.INSERT_DRIVE_FILE, color=ft.colors.BLUE_300),
                title=ft.Text("Document uploaded"),
                subtitle=ft.Text("2 minutes ago"),
                trailing=ft.Icon(ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN_400),
                shape=ft.RoundedRectangleBorder(radius=10),
            )
            for _ in range(5)
        ],
    )

    # Chart using matplotlib (example)
    # For simplicity we'll embed a placeholder image; you can replace with a real chart
    chart_image = ft.Image(
        src="https://quickchart.io/chart?c={type:'line',data:{labels:['Jan','Feb','Mar','Apr','May'],datasets:[{label:'Sales',data:[1000,1500,1200,1800,2000]}]}}",
        width=600,
        height=200,
        fit=ft.ImageFit.CONTAIN,
        border_radius=20,
    )

    chart_container = gradient_container(
        ft.Column([
            ft.Text("Sales Trend", size=20, weight=ft.FontWeight.BOLD),
            chart_image,
        ]),
        colors=[ft.colors.with_opacity(0.2, ft.colors.BLUE_900), ft.colors.with_opacity(0.2, ft.colors.PURPLE_900)],
    )

    # Right column with activities and chart
    right_column = ft.Column(
        controls=[
            gradient_container(
                ft.Column([
                    ft.Text("Recent Activities", size=20, weight=ft.FontWeight.BOLD),
                    activities,
                ]),
                colors=[ft.colors.with_opacity(0.3, ft.colors.GREY_800), ft.colors.with_opacity(0.1, ft.colors.GREY_900)],
            ),
            chart_container,
        ],
        spacing=20,
    )

    # Main layout: left column (header + stats) and right column
    layout = ft.Row(
        spacing=20,
        controls=[
            ft.Column(
                controls=[header, stats],
                spacing=20,
                expand=True,
            ),
            right_column,
        ],
    )

    # Add everything to the page
    page.add(layout)

    # Simulate updating stats with animation (just for effect)
    for _ in range(10):
        time.sleep(2)
        # Update some text values to show animation (in a real app you'd update actual data)
        stats.controls[0].content.controls[2].value = f"${random.randint(10000,15000)}"
        stats.controls[1].content.controls[2].value = str(random.randint(1000,2000))
        page.update()

ft.app(target=main)