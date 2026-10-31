import type { Metadata } from "next";
import "./globals.css";
import "./merchant-projects-v13.css";

export const metadata: Metadata = {
  title: "黑曼波工作台",
  description: "黑曼波工作台 V1.4 · 制作视频、发布任务、商家审核与订单管理",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
