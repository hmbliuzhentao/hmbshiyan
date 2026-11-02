import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "黑曼波工作台 V2.0",
  description: "黑曼波视频生产、团队协作与商家审核工作台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
