"use client";

import dynamic from "next/dynamic";
import "leaflet/dist/leaflet.css";
import "@/lib/leafletFix";
import { useEffect, useState } from "react";
import { WardLatest } from "@/types/ward";

// Dynamically import React-Leaflet components
// const MapContainer = dynamic(() => import("react-leaflet").then(mod => mod.MapContainer), { ssr: false }) as any;
// const TileLayer = dynamic(() => import("react-leaflet").then(mod => mod.TileLayer), { ssr: false }) as any;
// const Marker = dynamic(() => import("react-leaflet").then(mod => mod.Marker), { ssr: false }) as any;
// const Popup = dynamic(() => import("react-leaflet").then(mod => mod.Popup), { ssr: false }) as any;
// const LayersControl = dynamic(() => import("react-leaflet").then(mod => mod.LayersControl), { ssr: false }) as any;

import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  LayersControl,
  LayerGroup
} from "react-leaflet";

import { greenIcon, yellowIcon, redIcon } from "@/lib/leafletIcons";
import Link from "next/dist/client/link";

const { BaseLayer, Overlay } = LayersControl;

export default function WardMapPage() {
  const [wards, setWards] = useState<WardLatest[]>([]);
  const [error, setError] = useState("");
  const [criticalThreshold, setCriticalThreshold] = useState(80);


  useEffect(() => {
    fetch("http://localhost:8000/wards/latest", { credentials: "include" })
      .then(res => {
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        return res.json();
      })
      .then(data => setWards(data))
      .catch(err => {
        console.error("Ward fetch error", err);
        setError("Failed to load ward data");
      });
  }, []);

  function getIcon(avg: number) {
    if (avg >= criticalThreshold) return redIcon;
    if (avg >= criticalThreshold - 20) return yellowIcon;
    return greenIcon;
  }


  return (
    <>
      <h1 className="text-xl font-bold mb-4">Ward Risk Map</h1>
      {error && <p className="text-red-500">{error}</p>}
      <div className="my-4">
        <label className="block font-medium">
          Critical Threshold: {criticalThreshold}%
        </label>
        <input
          type="range"
          min={50}
          max={90}
          value={criticalThreshold}
          onChange={e => setCriticalThreshold(Number(e.target.value))}
          className="w-full"
        />
      </div>

      <MapContainer center={[12.97, 77.59]} zoom={12} style={{ height: "500px", width: "100%" }}>
        <LayersControl position="topright">
        <BaseLayer checked name="Street View">
            <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
        </BaseLayer>

        <BaseLayer name="Satellite View">
            <TileLayer
            attribution='Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics'
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            />
        </BaseLayer>

        <BaseLayer name="Hybrid View">
            <LayerGroup>
            <TileLayer
                attribution='Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics'
                url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            />
            <TileLayer
                attribution='Labels © Esri'
                url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
            />
            </LayerGroup>
        </BaseLayer>
        </LayersControl>


        {wards.map((w, idx) => (
          <Marker 
            key={`${w.ward}-${idx}`}
            position={[w.latitude, w.longitude]}
            icon={getIcon(w.avg_fill_level)}
          >
            <Popup>
              <b>Ward {w.ward}</b>
              <br />
              Avg Fill: {w.avg_fill_level}%
              <br />
              <Link href={`/dashboard/ward/${w.ward}`}>
                <button style={{ marginTop: "5px" }}>View Details</button>
              </Link>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      
      {wards.length === 0 && !error && <p>No ward data available</p>}
    </>
  );
}
