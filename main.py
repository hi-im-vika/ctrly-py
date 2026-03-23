import dearpygui.dearpygui as dpg

def main():
    print("Hello from ctrly-py!")
    dpg.create_context()
    dpg.create_viewport(title='Custom Title')

    with dpg.window(label="The Window",tag="Primary Window"):
        dpg.add_text("Hello, world")
        dpg.add_slider_int(label="Throttle", vertical=True, max_value=100, height=160)
        dpg.add_slider_int(label="Steering", vertical=True, max_value=100, height=160)
        with dpg.table(header_row=False):

            # use add_table_column to add columns to the table,
            # table columns use slot 0
            dpg.add_table_column()
            dpg.add_table_column()

            with dpg.table_row():
                dpg.add_text(f"Refresh rate")
                dpg.add_text(f"9000 hz")
            with dpg.table_row():
                dpg.add_text(f"Response time")
                dpg.add_text(f"0.1 ms")

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("Primary Window", True)
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == "__main__":
    main()