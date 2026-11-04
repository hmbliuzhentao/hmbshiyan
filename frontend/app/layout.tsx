import type { Metadata } from "next";
import catIcon from "./heimanbo-icon.png";
import "./globals.css";

export const metadata: Metadata = {
  title: "黑曼波工作台 V2.1.2",
  description: "黑曼波视频生产、团队协作与商家审核工作台",
  icons: {
    icon: [{ url: catIcon.src, type: "image/png" }],
    shortcut: [{ url: catIcon.src, type: "image/png" }],
    apple: [{ url: catIcon.src, type: "image/png" }],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
