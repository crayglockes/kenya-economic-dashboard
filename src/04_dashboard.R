# ============================================================================
# Kenya Economic Dashboard - Shiny App
# ============================================================================

library(shiny)
library(shinydashboard)
library(tidyverse)
library(plotly)
library(DT)

# Load data
library(here)
kenya_data <- read_csv(here("data", "processed", "kenya_economic_clean.csv"))

# UI
ui <- dashboardPage(
  dashboardHeader(title = "Kenya Economic Dashboard"),
  
  dashboardSidebar(
    sidebarMenu(
      menuItem("Overview", tabName = "overview", icon = icon("dashboard")),
      menuItem("GDP Analysis", tabName = "gdp", icon = icon("chart-line")),
      menuItem("Trade & Debt", tabName = "trade", icon = icon("balance-scale")),
      menuItem("Data Table", tabName = "data", icon = icon("table"))
    ),
    
    sliderInput("year_range", "Select Year Range:",
                min = min(kenya_data$year), max = max(kenya_data$year),
                value = c(min(kenya_data$year), max(kenya_data$year)),
                sep = "")
  ),
  
  dashboardBody(
    tabItems(
      # Overview tab
      tabItem(tabName = "overview",
              fluidRow(
                valueBoxOutput("gdp_box"),
                valueBoxOutput("growth_box"),
                valueBoxOutput("inflation_box")
              ),
              fluidRow(
                box(plotlyOutput("gdp_trend_plot"), width = 12)
              )
      ),
      
      # GDP tab
      tabItem(tabName = "gdp",
              fluidRow(
                box(plotlyOutput("gdp_growth_plot"), width = 6),
                box(plotlyOutput("inflation_plot"), width = 6)
              )
      ),
      
      # Trade tab
      tabItem(tabName = "trade",
              fluidRow(
                box(plotlyOutput("trade_plot"), width = 6),
                box(plotlyOutput("debt_plot"), width = 6)
              )
      ),
      
      # Data tab
      tabItem(tabName = "data",
              box(DTOutput("data_table"), width = 12)
      )
    )
  )
)

# Server
server <- function(input, output) {
  
  # Reactive filtered data
  filtered_data <- reactive({
    kenya_data %>%
      filter(year >= input$year_range[1], year <= input$year_range[2])
  })
  
  # Value boxes
  output$gdp_box <- renderValueBox({
    latest_gdp <- filtered_data() %>% slice_max(year) %>% pull(gdp_current_usd)
    valueBox(
      scales::dollar(latest_gdp, scale = 1e-9, suffix = "B"),
      "Latest GDP",
      icon = icon("money-bill-wave"),
      color = "green"
    )
  })
  
  output$growth_box <- renderValueBox({
    avg_growth <- mean(filtered_data()$gdp_growth_annual, na.rm = TRUE)
    valueBox(
      paste0(round(avg_growth, 1), "%"),
      "Avg. GDP Growth",
      icon = icon("chart-line"),
      color = "blue"
    )
  })
  
  output$inflation_box <- renderValueBox({
    avg_inflation <- mean(filtered_data()$inflation_cpi, na.rm = TRUE)
    valueBox(
      paste0(round(avg_inflation, 1), "%"),
      "Avg. Inflation",
      icon = icon("fire"),
      color = "orange"
    )
  })
  
  # Plots
  output$gdp_trend_plot <- renderPlotly({
    p <- ggplot(filtered_data(), aes(x = year, y = gdp_current_usd / 1e9)) +
      geom_line(color = "#006600", size = 1.2) +
      geom_point(color = "#006600") +
      labs(title = "GDP Trend", x = "Year", y = "GDP (Billions USD)") +
      theme_minimal()
    ggplotly(p)
  })
  
  output$gdp_growth_plot <- renderPlotly({
    p <- ggplot(filtered_data(), aes(x = year, y = gdp_growth_annual)) +
      geom_line(color = "#0066CC", size = 1) +
      geom_hline(yintercept = 0, linetype = "dashed", color = "red") +
      labs(title = "GDP Growth Rate", x = "Year", y = "Growth (%)") +
      theme_minimal()
    ggplotly(p)
  })
  
  output$inflation_plot <- renderPlotly({
    p <- ggplot(filtered_data(), aes(x = year, y = inflation_cpi)) +
      geom_line(color = "#FF6600", size = 1) +
      labs(title = "Inflation Rate", x = "Year", y = "Inflation (%)") +
      theme_minimal()
    ggplotly(p)
  })
  
  output$trade_plot <- renderPlotly({
    p <- ggplot(filtered_data(), aes(x = year, y = trade_balance_pct_gdp)) +
      geom_area(fill = "#CC0000", alpha = 0.3) +
      geom_line(color = "#CC0000") +
      labs(title = "Trade Balance", x = "Year", y = "% of GDP") +
      theme_minimal()
    ggplotly(p)
  })
  
  output$debt_plot <- renderPlotly({
    p <- ggplot(filtered_data(), aes(x = year, y = debt_to_gdp_ratio)) +
      geom_line(color = "#CC0000", size = 1) +
      geom_hline(yintercept = 60, linetype = "dashed") +
      labs(title = "Debt-to-GDP Ratio", x = "Year", y = "%") +
      theme_minimal()
    ggplotly(p)
  })
  
  output$data_table <- renderDT({
    filtered_data() %>%
      select(year, gdp_current_usd, gdp_growth_annual, inflation_cpi, 
             trade_balance_pct_gdp, debt_to_gdp_ratio) %>%
      datatable(options = list(pageLength = 15))
  })
}

# Run app
shinyApp(ui, server)