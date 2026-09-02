// BuyerAgentApp.tsx
import { useState } from "react";
import { ChatPanel } from "./ChatPanel";
import { WireTrace } from "./WireTrace";
import { useAgentSession } from "./useAgentSession";
import { colors } from "./tokens";

export function BuyerAgentApp() {
  const { state, start } = useAgentSession();
  const [mobileTab, setMobileTab] = useState<"chat" | "wire">("chat");

  return (
    <div className="h-screen w-screen flex flex-col md:flex-row overflow-hidden">
      {/* Mobile Tab Header */}
      <div
        className="md:hidden flex"
        style={{ borderBottom: `1px solid ${colors.ink}14` }}
      >
        {(["chat", "wire"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setMobileTab(tab)}
            className="flex-1 py-2.5 text-sm capitalize"
            style={{
              backgroundColor: mobileTab === tab ? colors.cream : colors.charcoal,
              color: mobileTab === tab ? colors.ink : `${colors.cream}90`,
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Chat Panel - Human Register */}
      <div className={`${mobileTab === "chat" ? "flex" : "hidden"} md:flex md:w-[52%] h-full`}>
        <ChatPanel state={state} onStart={start} />
      </div>

      {/* Wire Trace - Machine Register */}
      <div className={`${mobileTab === "wire" ? "flex" : "hidden"} md:flex md:w-[48%] h-full`}>
        <WireTrace events={state.wire} />
      </div>
    </div>
  );
}
