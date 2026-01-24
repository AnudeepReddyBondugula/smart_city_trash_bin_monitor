'use client';

import dynamic from "next/dynamic";
const MapView = dynamic(() => import("@/components/MapView"), {ssr: false,});


export default function MapPage() {
    return (
        <div className="w-full h-screen flex items-center justify-center">
            <section>
                <h2 className="text-lg font-semibold">Ward Map View</h2>
                <MapView />
            </section>
        </div>
    );
}