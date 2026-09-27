import { Ionicons } from "@expo/vector-icons";
import { CameraView, useCameraPermissions } from "expo-camera";
import { router } from "expo-router";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { OpenFoodFactsReviewSheet } from "@/components/openfoodfacts-review-sheet";
import {
  createPantryItem,
  lookupBarcode,
  type OpenFoodFactsProductDraft,
  type PantryItemCreateInput,
} from "@/lib/pantry";

export default function BarcodeScannerScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState<OpenFoodFactsProductDraft | null>(null);
  const [showReview, setShowReview] = useState(false);
  const [manualBarcode, setManualBarcode] = useState("");
  const [showManualInput, setShowManualInput] = useState(false);
  const [torch, setTorch] = useState(false);

  const insets = useSafeAreaInsets();

  async function handleBarcode(rawBarcode: string) {
    const cleanedBarcode = rawBarcode.trim();
    if (!cleanedBarcode || loading) return;

    setLoading(true);
    setScanned(true);

    try {
      const productDraft = await lookupBarcode(cleanedBarcode);
      setDraft(productDraft);
      setShowReview(true);
    } catch {
      Alert.alert(
        "Erreur de recherche",
        "Impossible de récupérer les informations du produit. Voulez-vous le créer manuellement ?",
        [
          { text: "Annuler", style: "cancel", onPress: () => setScanned(false) },
          {
            text: "Créer",
            onPress: () => {
              setDraft({
                barcode: cleanedBarcode,
                found: false,
                raw_name: null,
                brand: null,
                suggested_name: "",
                quantity: 1,
                unit: "item",
                category: "Épicerie",
                image_url: null,
                nutriscore: null,
                packaging: null,
                location: "Placard",
                missing_fields: ["name", "expires_at"],
              });
              setShowReview(true);
            },
          },
        ]
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmPantryItem(payload: PantryItemCreateInput) {
    await createPantryItem(payload);
    setShowReview(false);
    router.back();
  }

  function handleCloseReview() {
    setShowReview(false);
    setScanned(false);
    setDraft(null);
  }

  if (!permission) {
    return (
      <View style={[styles.container, styles.centered]}>
        <ActivityIndicator size="large" color="#059669" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {!permission.granted ? (
        <View style={[styles.centered, { paddingHorizontal: 24 }]}>
          <Ionicons name="camera-outline" size={64} color="#64748b" />
          <Text style={styles.permissionTitle}>{"Accès à l'appareil photo"}</Text>
          <Text style={styles.permissionSubtitle}>
            AdamHUB a besoin de la caméra pour scanner les codes-barres de vos produits alimentaires.
          </Text>
          <Pressable style={styles.permissionButton} onPress={requestPermission}>
            <Text style={styles.permissionButtonText}>Autoriser la caméra</Text>
          </Pressable>
          <Pressable
            style={styles.manualFallbackButton}
            onPress={() => setShowManualInput(true)}
          >
            <Text style={styles.manualFallbackText}>Saisir le code-barres manuellement</Text>
          </Pressable>
        </View>
      ) : (
        <CameraView
          style={StyleSheet.absoluteFill}
          facing="back"
          enableTorch={torch}
          barcodeScannerSettings={{
            barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e", "code128"],
          }}
          onBarcodeScanned={scanned || loading ? undefined : ({ data }) => handleBarcode(data)}
        >
          {/* Overlay with cutout/viewfinder */}
          <View style={styles.overlay}>
            {/* Top Bar */}
            <View style={[styles.topBar, { paddingTop: insets.top + 8 }]}>
              <Pressable
                onPress={() => router.back()}
                style={styles.circleButton}
                hitSlop={8}
              >
                <Ionicons name="close" size={24} color="#ffffff" />
              </Pressable>
              <Text style={styles.topBarTitle}>Scanner un code-barres</Text>
              <Pressable
                onPress={() => setTorch((prev) => !prev)}
                style={[styles.circleButton, torch && styles.circleButtonActive]}
                hitSlop={8}
              >
                <Ionicons
                  name={torch ? "flash" : "flash-outline"}
                  size={20}
                  color={torch ? "#059669" : "#ffffff"}
                />
              </Pressable>
            </View>

            {/* Viewfinder Target */}
            <View style={styles.viewfinderContainer}>
              <View style={styles.viewfinderBox}>
                <View style={[styles.corner, styles.cornerTL]} />
                <View style={[styles.corner, styles.cornerTR]} />
                <View style={[styles.corner, styles.cornerBL]} />
                <View style={[styles.corner, styles.cornerBR]} />
                {loading ? (
                  <View style={styles.loadingBox}>
                    <ActivityIndicator size="large" color="#10b981" />
                    <Text style={styles.loadingText}>Recherche Open Food Facts...</Text>
                  </View>
                ) : null}
              </View>
              <Text style={styles.instructionText}>
                {"Alignez le code-barres à l'intérieur du cadre"}
              </Text>
            </View>

            {/* Bottom Actions */}
            <View style={[styles.bottomBar, { paddingBottom: insets.bottom + 16 }]}>
              <Pressable
                style={styles.manualEntryButton}
                onPress={() => setShowManualInput((prev) => !prev)}
              >
                <Ionicons name="keypad-outline" size={18} color="#ffffff" />
                <Text style={styles.manualEntryButtonText}>
                  {showManualInput ? "Masquer la saisie manuelle" : "Saisie manuelle du code"}
                </Text>
              </Pressable>
            </View>
          </View>
        </CameraView>
      )}

      {/* Manual Barcode Input Sheet / Drawer */}
      {showManualInput ? (
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={styles.manualInputContainer}
        >
          <View style={styles.manualInputCard}>
            <Text style={styles.manualInputTitle}>Saisie manuelle du code EAN</Text>
            <View style={styles.inputRow}>
              <TextInput
                style={styles.barcodeInput}
                value={manualBarcode}
                onChangeText={setManualBarcode}
                placeholder="Ex: 3560070557451"
                placeholderTextColor="#94a3b8"
                keyboardType="numeric"
                autoFocus
              />
              <Pressable
                style={[
                  styles.lookupButton,
                  (!manualBarcode.trim() || loading) && styles.lookupButtonDisabled,
                ]}
                disabled={!manualBarcode.trim() || loading}
                onPress={() => handleBarcode(manualBarcode)}
              >
                {loading ? (
                  <ActivityIndicator size="small" color="#ffffff" />
                ) : (
                  <Ionicons name="arrow-forward" size={20} color="#ffffff" />
                )}
              </Pressable>
            </View>
          </View>
        </KeyboardAvoidingView>
      ) : null}

      {/* Open Food Facts Review Sheet */}
      <OpenFoodFactsReviewSheet
        visible={showReview}
        draft={draft}
        onClose={handleCloseReview}
        onConfirm={handleConfirmPantryItem}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#000000",
  },
  centered: {
    justifyContent: "center",
    alignItems: "center",
  },
  permissionTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#0f172a",
    marginTop: 16,
    textAlign: "center",
  },
  permissionSubtitle: {
    fontSize: 14,
    color: "#64748b",
    marginTop: 8,
    textAlign: "center",
    lineHeight: 20,
  },
  permissionButton: {
    marginTop: 24,
    backgroundColor: "#059669",
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 12,
  },
  permissionButtonText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
  manualFallbackButton: {
    marginTop: 16,
    paddingVertical: 8,
  },
  manualFallbackText: {
    color: "#059669",
    fontSize: 14,
    fontWeight: "500",
  },
  overlay: {
    ...StyleSheet.absoluteFill,
    justifyContent: "space-between",
  },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
  },
  topBarTitle: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "600",
  },
  circleButton: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    justifyContent: "center",
    alignItems: "center",
  },
  circleButtonActive: {
    backgroundColor: "#ffffff",
  },
  viewfinderContainer: {
    alignItems: "center",
    justifyContent: "center",
  },
  viewfinderBox: {
    width: 270,
    height: 180,
    borderRadius: 16,
    position: "relative",
    justifyContent: "center",
    alignItems: "center",
  },
  corner: {
    position: "absolute",
    width: 28,
    height: 28,
    borderColor: "#10b981",
  },
  cornerTL: {
    top: 0,
    left: 0,
    borderTopWidth: 4,
    borderLeftWidth: 4,
    borderTopLeftRadius: 16,
  },
  cornerTR: {
    top: 0,
    right: 0,
    borderTopWidth: 4,
    borderRightWidth: 4,
    borderTopRightRadius: 16,
  },
  cornerBL: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 4,
    borderLeftWidth: 4,
    borderBottomLeftRadius: 16,
  },
  cornerBR: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 4,
    borderRightWidth: 4,
    borderBottomRightRadius: 16,
  },
  loadingBox: {
    backgroundColor: "rgba(15, 23, 42, 0.85)",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: "center",
    gap: 8,
  },
  loadingText: {
    color: "#ffffff",
    fontSize: 13,
    fontWeight: "500",
  },
  instructionText: {
    color: "rgba(255, 255, 255, 0.8)",
    fontSize: 13,
    marginTop: 20,
    textAlign: "center",
  },
  bottomBar: {
    alignItems: "center",
    paddingHorizontal: 20,
  },
  manualEntryButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "rgba(15, 23, 42, 0.75)",
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.2)",
  },
  manualEntryButtonText: {
    color: "#ffffff",
    fontSize: 14,
    fontWeight: "500",
  },
  manualInputContainer: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
  },
  manualInputCard: {
    backgroundColor: "#ffffff",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 36,
  },
  manualInputTitle: {
    fontSize: 15,
    fontWeight: "600",
    color: "#0f172a",
    marginBottom: 12,
  },
  inputRow: {
    flexDirection: "row",
    gap: 10,
  },
  barcodeInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: "#0f172a",
    backgroundColor: "#f8fafc",
  },
  lookupButton: {
    backgroundColor: "#059669",
    width: 48,
    height: 48,
    borderRadius: 12,
    justifyContent: "center",
    alignItems: "center",
  },
  lookupButtonDisabled: {
    backgroundColor: "#94a3b8",
  },
});
