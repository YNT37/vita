type PageContainerProps = {
  children: React.ReactNode;
  className?: string;
  /** 桌面端更宽（统计/管家等） */
  wide?: boolean;
};

export function PageContainer({
  children,
  className = "",
  wide = false,
}: PageContainerProps) {
  const width = wide
    ? "max-w-5xl xl:max-w-6xl"
    : "max-w-2xl md:max-w-3xl lg:max-w-4xl";

  return (
    <main
      className={`flex-1 w-full mx-auto min-w-0 px-4 py-4 sm:px-6 sm:py-5 ${width} ${className}`}
    >
      {children}
    </main>
  );
}
