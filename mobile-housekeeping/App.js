import React, { useMemo } from "react";
import { SafeAreaView, ScrollView, StyleSheet, Text, View } from "react-native";

const demoTasks = [
  { room: "RM-0101", type: "prepare_room", status: "new", priority: 1 },
  { room: "RM-0410", type: "cleaning", status: "in_progress", priority: 2 },
  { room: "RS-0205", type: "repair", status: "new", priority: 3 },
];

export default function App() {
  const sorted = useMemo(() => [...demoTasks].sort((a, b) => a.priority - b.priority), []);

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Housekeeping Board</Text>
        <Text style={styles.subtitle}>React Native view for maids and supervisors</Text>
        {sorted.map((item, index) => (
          <View style={styles.card} key={index}>
            <Text style={styles.room}>{item.room}</Text>
            <Text style={styles.meta}>{item.type}</Text>
            <Text style={styles.meta}>status: {item.status}</Text>
            <Text style={styles.meta}>priority: {item.priority}</Text>
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#f2f5f8",
  },
  content: {
    padding: 20,
    gap: 12,
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    color: "#102a43",
  },
  subtitle: {
    color: "#486581",
    marginBottom: 8,
  },
  card: {
    backgroundColor: "#ffffff",
    borderRadius: 16,
    padding: 14,
    shadowColor: "#102a43",
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  room: {
    fontSize: 20,
    fontWeight: "600",
    color: "#243b53",
  },
  meta: {
    color: "#486581",
    marginTop: 4,
  },
});
