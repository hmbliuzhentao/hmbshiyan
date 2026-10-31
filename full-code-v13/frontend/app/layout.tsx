import type { Metadata } from "next";
import "./globals.css";
import "./merchant-projects-v13.css";

export const metadata: Metadata = {
  title: "黑曼波工作台",
  description: "黑曼波工作台 · 视频拍摄、制作、剪辑与接单管理",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
