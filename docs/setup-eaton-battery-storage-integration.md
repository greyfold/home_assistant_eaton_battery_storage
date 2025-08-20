# Eaton Battery Storage installation

- Navigate to **HACS** in the menu of your Home Assistant

    ![HACS](https://raw.githubusercontent.com/greyfold/home_assistant_eaton_xstorage_home/refs/heads/main/images/hacs-menu-link.png "Click on HACS")

- Use the top right 3 dots icon to add a custom repository.

    ![Add custom integration](https://raw.githubusercontent.com/greyfold/home_assistant_eaton_xstorage_home/refs/heads/main/images/hacs-link-custom-repository.png "Add custom integration")

- Enter the URL `https://github.com/greyfold/home_assistant_eaton_battery_storage` in the **Repository** field and select **Integration** as a type, then click on **Add**.

    ![Install Eaton Battery Storage](https://raw.githubusercontent.com/greyfold/home_assistant_eaton_xstorage_home/refs/heads/main/images/hacs-set-custom-repository.png "Install Eaton Battery Storage")

- Close the modal an look for the integration, by searching for **Eaton Battery Storage System**, click on the result and finally click on **Download** located on the bottom right corner of your browser.

- Navigate to **Settings** > **Devices & services**, then click on **Add integration** located on the bottom right corner of your browser.
- Type **Eaton Battery Storage System**, click on the result. Then enter the credentials for your xStorage Home unit (Same used to access the local UI) and hit submit.

> Congratulations, you should now have access to your **Eaton xStorage Home** metrics in Home Assistant