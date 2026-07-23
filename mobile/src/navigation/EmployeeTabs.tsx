import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";

import ClockScreen from "../screens/employee/ClockScreen";
import ScheduleScreen from "../screens/employee/ScheduleScreen";
import PtoScreen from "../screens/employee/PtoScreen";
import MoreStackNavigator from "./MoreStack";

const Tab = createBottomTabNavigator();

export default function EmployeeTabs() {
  return (
    <Tab.Navigator screenOptions={{ tabBarActiveTintColor: "#a8641f" }}>
      <Tab.Screen name="Clock" component={ClockScreen} options={{ headerShown: false }} />
      <Tab.Screen name="Schedule" component={ScheduleScreen} options={{ headerShown: false }} />
      <Tab.Screen name="Time Off" component={PtoScreen} options={{ headerShown: false }} />
      <Tab.Screen name="More" component={MoreStackNavigator} options={{ headerShown: false }} />
    </Tab.Navigator>
  );
}
