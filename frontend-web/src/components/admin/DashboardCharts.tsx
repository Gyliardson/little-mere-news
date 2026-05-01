"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";

const COLORS = ["#00FFFF", "#008080", "#40E0D0", "#20B2AA", "#5F9EA0"];

const t = {
  pt: {
    dailyVolume: "Volume de Processamento Diário",
    categoryDist: "Distribuição de Categorias",
    noData: "Sem dados suficientes para exibir o gráfico.",
  },
  en: {
    dailyVolume: "Daily Processing Volume",
    categoryDist: "Category Distribution",
    noData: "Not enough data to display the chart.",
  },
};

interface DailyData {
  name: string;
  count: number;
}

interface CategoryData {
  name: string;
  value: number;
}

export default function DashboardCharts({
  lang,
  dailyData,
  categoryData,
}: {
  lang: string;
  dailyData: DailyData[];
  categoryData: CategoryData[];
}) {
  const labels = lang === "pt" ? t.pt : t.en;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      {/* Daily Volume Bar Chart */}
      <div
        className="p-6 bg-background-secondary border border-primary/20 rounded-2xl flex flex-col"
        style={{ minHeight: "24rem" }}
      >
        <h3 className="text-lg font-bold mb-6 text-foreground">
          {labels.dailyVolume}
        </h3>
        <div className="flex-1" style={{ minHeight: "16rem" }}>
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
              <BarChart
                data={dailyData}
                margin={{ top: 0, right: 0, left: -20, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#008080"
                  opacity={0.2}
                />
                <XAxis
                  dataKey="name"
                  stroke="#CCCCCC"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke="#CCCCCC"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1A1A1A",
                    borderColor: "#008080",
                    borderRadius: "8px",
                  }}
                  itemStyle={{ color: "#F5F5F5" }}
                />
                <Bar
                  dataKey="count"
                  fill="#00FFFF"
                  radius={[4, 4, 4, 4]}
                  name={lang === "pt" ? "Artigos" : "Articles"}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-foreground-muted text-sm">
              {labels.noData}
            </div>
          )}
        </div>
      </div>

      {/* Category Distribution Pie Chart */}
      <div
        className="p-6 bg-background-secondary border border-primary/20 rounded-2xl flex flex-col"
        style={{ minHeight: "24rem" }}
      >
        <h3 className="text-lg font-bold mb-6 text-foreground">
          {labels.categoryDist}
        </h3>
        <div className="flex-1" style={{ minHeight: "16rem" }}>
          {categoryData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
              <PieChart>
                <Pie
                  data={categoryData}
                  cx="50%"
                  cy="45%"
                  innerRadius="50%"
                  outerRadius="70%"
                  paddingAngle={5}
                  dataKey="value"
                  stroke="none"
                >
                  {categoryData.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1A1A1A",
                    borderColor: "#008080",
                    borderRadius: "8px",
                  }}
                  itemStyle={{ color: "#F5F5F5" }}
                />
                <Legend
                  verticalAlign="bottom"
                  align="center"
                  iconType="circle"
                  iconSize={10}
                  wrapperStyle={{
                    color: "#999999",
                    fontSize: "12px",
                    paddingTop: "8px",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-foreground-muted text-sm">
              {labels.noData}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
